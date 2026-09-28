"""Small subprocess boundary used by platform adapters."""

from __future__ import annotations

import ctypes
import os
import signal
import subprocess
import sys
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .errors import AppError


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    def __call__(self, command: list[str], timeout: int) -> CommandResult: ...


def yt_dlp_command(*arguments: str) -> list[str]:
    """Run the packaged yt-dlp with the same interpreter as the MCP service."""
    return [sys.executable, "-m", "yt_dlp", *arguments]


def _command_kind(command: list[str]) -> str:
    if "-m" in command:
        module_index = command.index("-m") + 1
        if module_index < len(command) and command[module_index] == "yt_dlp":
            return "yt-dlp"
    name = Path(command[0]).name.lower() if command else "command"
    if name in {"ffmpeg", "ffmpeg.exe"}:
        return "ffmpeg"
    if name in {"ffprobe", "ffprobe.exe"}:
        return "ffprobe"
    return name or "command"


class _JobIoCounters(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class _JobBasicLimitInformation(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", ctypes.c_uint32),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_uint32),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_uint32),
        ("SchedulingClass", ctypes.c_uint32),
    ]


class _JobExtendedInformation(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JobBasicLimitInformation),
        ("IoInfo", _JobIoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class _WindowsJob:
    """Best-effort Job Object so timeout cleanup includes grandchildren."""

    _KILL_ON_CLOSE = 0x00002000
    _EXTENDED_LIMIT_INFORMATION = 9

    def __init__(self, process: subprocess.Popen[str]) -> None:
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self._kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        self._kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        self._kernel32.SetInformationJobObject.restype = wintypes.BOOL
        self._kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self._kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        self._kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self._kernel32.TerminateJobObject.restype = wintypes.BOOL
        self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self._kernel32.CloseHandle.restype = wintypes.BOOL
        self._handle = self._kernel32.CreateJobObjectW(None, None)
        self.assigned = False
        if not self._handle:
            return
        information = _JobExtendedInformation()
        information.BasicLimitInformation.LimitFlags = self._KILL_ON_CLOSE
        configured = self._kernel32.SetInformationJobObject(
            self._handle,
            self._EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(information),
            ctypes.sizeof(information),
        )
        if not configured:
            self.close()
            return
        self.assigned = bool(
            self._kernel32.AssignProcessToJobObject(
                self._handle,
                wintypes.HANDLE(int(process._handle)),  # type: ignore[attr-defined]
            )
        )

    def terminate(self) -> None:
        if self._handle and self.assigned:
            self._kernel32.TerminateJobObject(self._handle, 1)

    def close(self) -> None:
        if self._handle:
            self._kernel32.CloseHandle(self._handle)
            self._handle = None


def _start_process(command: list[str]) -> tuple[subprocess.Popen[str], _WindowsJob | None]:
    kwargs: dict[str, object] = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
    }
    job: _WindowsJob | None = None
    if os.name == "nt":
        kwargs["creationflags"] = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    else:
        kwargs["start_new_session"] = True
    process = subprocess.Popen(command, **kwargs)  # type: ignore[arg-type]
    if os.name == "nt":
        try:
            job = _WindowsJob(process)
        except (AttributeError, OSError):
            job = None
    return process, job


def _terminate_process_tree(process: subprocess.Popen[str], job: _WindowsJob | None) -> None:
    if os.name == "nt":
        if job is not None and job.assigned:
            job.terminate()
        else:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                check=False,
            )
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            process.kill()


def run_command(command: list[str], timeout: int) -> CommandResult:
    job: _WindowsJob | None = None
    try:
        process, job = _start_process(command)
        stdout, stderr = process.communicate(timeout=timeout)
    except FileNotFoundError as exc:
        raise AppError(
            "missing_dependency",
            f"找不到运行依赖：{command[0]}。请先运行 doctor。",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        _terminate_process_tree(process, job)
        try:
            process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
        command_kind = _command_kind(command)
        raise AppError(
            "command_timeout",
            f"{command_kind} 执行超过 {timeout} 秒，已停止。",
            retryable=False,
            details={
                "phase": command_kind,
                "timeout_seconds": timeout,
                "command_kind": command_kind,
            },
        ) from exc
    finally:
        if job is not None:
            job.close()
    return CommandResult(process.returncode, stdout, stderr)
