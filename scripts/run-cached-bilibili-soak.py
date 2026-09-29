"""Run a bounded, strictly no-paid cached Bilibili stability soak."""

from __future__ import annotations

import argparse
import ctypes
import os
import shutil
import sys
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

from video_to_obsidian.config import load_settings
from video_to_obsidian.errors import AppError
from video_to_obsidian.pipeline import (
    _fingerprint,
    analyze_bilibili,
    default_bilibili_dependencies,
)
from video_to_obsidian.platforms.bilibili import resolve_input
from video_to_obsidian.preferences import effective_instruction
from video_to_obsidian.state import read_json, write_json


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _working_set_bytes() -> int:
    if os.name != "nt":
        return 0

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    process = ctypes.windll.kernel32.GetCurrentProcess()
    ok = ctypes.windll.psapi.GetProcessMemoryInfo(
        process,
        ctypes.byref(counters),
        counters.cb,
    )
    return int(counters.WorkingSetSize) if ok else 0


def _history_count(settings, identity: str) -> int:
    directory = settings.paths.state / "history" / "bilibili" / identity
    return len(list(directory.glob("*.json"))) if directory.is_dir() else 0


def _block_paid_stage(*_args: Any, **_kwargs: Any):
    raise AppError(
        "soak_paid_stage_blocked",
        "稳定性巡检禁止进入 Kimi 阶段。",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("share_text")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not 1 <= args.iterations <= 240:
        raise SystemExit("iterations must be between 1 and 240")
    if not 0 <= args.interval_seconds <= 3600:
        raise SystemExit("interval-seconds must be between 0 and 3600")

    settings = load_settings(args.config)
    resolved = resolve_input(args.share_text)
    part = int(resolved.part or 1)
    identity = f"bilibili_{resolved.bvid}_p{part:02d}"
    manifest_path = settings.paths.state / "bilibili" / f"{identity}.json"
    output = args.output or (
        settings.paths.state / "stability" / f"{identity}.cached-soak.json"
    )
    dependencies = replace(
        default_bilibili_dependencies(settings),
        kimi=_block_paid_stage,
    )
    history_before = _history_count(settings, identity)
    samples: list[dict[str, Any]] = []
    report: dict[str, Any] = {
        "schema_version": 1,
        "kind": "cached_bilibili_soak",
        "identity": identity,
        "started_at": _now(),
        "status": "running",
        "iterations_requested": args.iterations,
        "iterations_completed": 0,
        "interval_seconds": args.interval_seconds,
        "history_before": history_before,
        "paid_call_performed": False,
        "samples": samples,
    }
    write_json(output, report)

    try:
        for index in range(args.iterations):
            instruction, _ = effective_instruction(settings, "")
            expected_fingerprint = _fingerprint("vision", instruction, settings)
            manifest = read_json(manifest_path)
            saved_to = Path(str(manifest.get("saved_to") or ""))
            if not (
                manifest.get("status") == "completed"
                and manifest.get("request_fingerprint") == expected_fingerprint
                and saved_to.is_file()
            ):
                raise AppError(
                    "soak_cache_precondition_failed",
                    "缓存前置条件发生变化，稳定性巡检已在分析前停止。",
                )

            started = time.monotonic()
            result = analyze_bilibili(
                args.share_text,
                settings=settings,
                dependencies=dependencies,
            )
            elapsed = time.monotonic() - started
            history_now = _history_count(settings, identity)
            if not result.get("cached") or history_now != history_before:
                raise AppError(
                    "soak_cache_invariant_failed",
                    "缓存或 Kimi 历史计数发生变化，稳定性巡检已停止。",
                )

            samples.append(
                {
                    "iteration": index + 1,
                    "elapsed_seconds": round(elapsed, 3),
                    "working_set_bytes": _working_set_bytes(),
                    "free_disk_bytes": int(shutil.disk_usage(settings.paths.state).free),
                    "cached": True,
                    "history_count": history_now,
                }
            )
            report["iterations_completed"] = index + 1
            report["updated_at"] = _now()
            write_json(output, report)
            if index + 1 < args.iterations:
                time.sleep(args.interval_seconds)
    except AppError as exc:
        report.update(
            {
                "status": "failed",
                "finished_at": _now(),
                "error_code": exc.code,
                "history_after": _history_count(settings, identity),
            }
        )
        write_json(output, report)
        return 1
    except Exception as exc:  # never persist provider or command text
        report.update(
            {
                "status": "failed",
                "finished_at": _now(),
                "error_code": f"internal_{type(exc).__name__}",
                "history_after": _history_count(settings, identity),
            }
        )
        write_json(output, report)
        return 1

    report.update(
        {
            "status": "completed",
            "finished_at": _now(),
            "history_after": _history_count(settings, identity),
            "all_cached": True,
            "max_working_set_bytes": max(
                (int(item["working_set_bytes"]) for item in samples), default=0
            ),
            "min_free_disk_bytes": min(
                (int(item["free_disk_bytes"]) for item in samples), default=0
            ),
        }
    )
    write_json(output, report)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
