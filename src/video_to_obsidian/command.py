"""Small subprocess boundary used by platform adapters."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
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


def run_command(command: list[str], timeout: int) -> CommandResult:
    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise AppError(
            "missing_dependency",
            f"找不到运行依赖：{command[0]}。请先运行 doctor。",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise AppError(
            "command_timeout",
            f"{command[0]} 执行超时。",
            retryable=True,
        ) from exc
    return CommandResult(process.returncode, process.stdout, process.stderr)
