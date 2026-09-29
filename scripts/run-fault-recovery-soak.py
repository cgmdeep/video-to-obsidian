"""Exercise repeated checkpoint recovery without network or paid model calls."""

from __future__ import annotations

import argparse
import ctypes
import gc
import json
import os
import sys
import tempfile
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from video_to_obsidian.config import initialize_settings, load_settings
from video_to_obsidian.errors import AppError
from video_to_obsidian.kimi import KimiResult
from video_to_obsidian.media import PreparedVideo
from video_to_obsidian.pipeline import BilibiliDependencies, analyze_bilibili
from video_to_obsidian.platforms.bilibili import BilibiliMetadata, ResolvedBilibili
from video_to_obsidian.state import read_json, write_json


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _working_set_bytes() -> int:
    if os.name == "nt":
        from ctypes import wintypes

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
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
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = (
            wintypes.HANDLE,
            ctypes.POINTER(ProcessMemoryCounters),
            wintypes.DWORD,
        )
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        ok = psapi.GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        )
        return int(counters.WorkingSetSize) if ok else 0

    try:
        import resource

        maximum = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        return maximum if sys.platform == "darwin" else maximum * 1024
    except (ImportError, ValueError):
        return 0


class FaultFixture:
    def __init__(self) -> None:
        self.downloads: dict[str, int] = defaultdict(int)
        self.kimi_attempts: dict[str, int] = defaultdict(int)

    def dependencies(self) -> BilibiliDependencies:
        def resolve(text: str) -> ResolvedBilibili:
            bvid = text.strip()
            return ResolvedBilibili(
                bvid=bvid,
                part=None,
                canonical_url=f"https://www.bilibili.com/video/{bvid}",
                input_kind="fault_fixture",
            )

        def metadata(resolved: ResolvedBilibili, _settings: Any) -> BilibiliMetadata:
            return BilibiliMetadata(
                identity=f"bilibili_{resolved.bvid}_p01",
                bvid=resolved.bvid,
                part=1,
                url=resolved.canonical_url,
                title=f"故障恢复样本 {resolved.bvid}",
                uploader="本地验收夹具",
                uploader_id="fixture",
                duration=60,
                upload_date="20260930",
                description="不访问网络、不调用付费模型。",
                tags=("稳定性",),
                yt_dlp_id=resolved.bvid,
                download_auth="local_fixture",
            )

        def download(
            resolved: ResolvedBilibili,
            _metadata: BilibiliMetadata,
            output: Path,
            _settings: Any,
        ) -> Path:
            self.downloads[resolved.bvid] += 1
            path = output / "source.mp4"
            path.write_bytes((resolved.bvid.encode("ascii") + b"\0") * 4096)
            return path

        def kimi(
            _video: Path,
            metadata_value: dict[str, Any],
            _mode: str,
            _instruction: str,
            _is_proxy: bool,
        ) -> KimiResult:
            identity = str(metadata_value["identity"])
            self.kimi_attempts[identity] += 1
            if self.kimi_attempts[identity] == 1:
                raise AppError(
                    "kimi_upstream_failed",
                    "故障注入：模拟 Kimi HTTP 503。",
                    retryable=True,
                    details={
                        "phase": "analysis",
                        "http_status": 503,
                        "kimi_attempts": 1,
                    },
                )
            return KimiResult(
                "### 内容速览\n" + "故障恢复后生成的本地验收正文。" * 12,
                ("稳定性", "故障恢复"),
                (),
                {
                    "kimi_attempts": 1,
                    "finish_reason": "stop",
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0},
                    "model": "local-fault-fixture",
                },
            )

        return BilibiliDependencies(
            resolve=resolve,
            metadata=metadata,
            download=download,
            probe=lambda path: {
                "has_video": True,
                "has_audio": True,
                "duration": 60,
                "size_bytes": path.stat().st_size,
            },
            prepare=lambda video, _duration, _checkpoint, _settings: PreparedVideo(
                video, False
            ),
            kimi=kimi,
            transcript=lambda *_args: (_ for _ in ()).throw(
                AssertionError("standard profile must not transcribe")
            ),
        )


def _run(iterations: int, output: Path) -> dict[str, Any]:
    started_at = _now()
    memory_before = _working_set_bytes()
    fixture = FaultFixture()
    samples: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="vto-fault-soak-") as temporary:
        root = Path(temporary)
        config = initialize_settings(
            root / "vault",
            config_path=root / "config.toml",
            runtime_root=root / "runtime",
        )
        settings = load_settings(config)
        dependencies = fixture.dependencies()

        for index in range(1, iterations + 1):
            bvid = f"BV{index:010d}"
            identity = f"bilibili_{bvid}_p01"
            manifest_path = settings.paths.state / "bilibili" / f"{identity}.json"
            began = time.monotonic()

            try:
                analyze_bilibili(
                    bvid, settings=settings, dependencies=dependencies
                )
            except AppError as exc:
                if not (
                    exc.code == "kimi_upstream_failed"
                    and exc.retryable
                    and exc.details.get("source_checkpoint_exists") is True
                    and exc.details.get("checkpoint_reusable") is True
                ):
                    raise
            else:
                raise AssertionError("fault injection did not stop the first attempt")

            failed_manifest = read_json(manifest_path)
            source_path = Path(str(failed_manifest.get("source_path") or ""))
            if failed_manifest.get("status") != "failed" or not source_path.is_file():
                raise AssertionError("failed attempt did not preserve a source checkpoint")

            recovered = analyze_bilibili(
                bvid, settings=settings, dependencies=dependencies
            )
            cached = analyze_bilibili(
                bvid, settings=settings, dependencies=dependencies
            )
            histories = list(
                (settings.paths.state / "history" / "bilibili" / identity).glob(
                    "*.json"
                )
            )
            outcomes = sorted(
                str(read_json(path).get("outcome") or "") for path in histories
            )
            final_manifest = read_json(manifest_path)
            if not (
                recovered.get("complete") is True
                and cached.get("cached") is True
                and fixture.downloads[bvid] == 1
                and fixture.kimi_attempts[identity] == 2
                and outcomes == ["completed", "failed"]
                and final_manifest.get("source_path") == ""
                and not source_path.exists()
            ):
                raise AssertionError("fault recovery invariant failed")

            leaked_media = [
                str(path.relative_to(root))
                for path in (root / "runtime").rglob("*")
                if path.is_file()
                and path.suffix.lower() in {".mp4", ".wav", ".part", ".tmp"}
            ]
            if leaked_media:
                raise AssertionError("temporary media leaked after recovery")

            gc.collect()
            samples.append(
                {
                    "iteration": index,
                    "elapsed_seconds": round(time.monotonic() - began, 4),
                    "download_count": 1,
                    "simulated_kimi_attempts": 2,
                    "history_outcomes": outcomes,
                    "cached_repeat": True,
                    "temporary_media_files": 0,
                    "working_set_bytes": _working_set_bytes(),
                }
            )

    memory_after = _working_set_bytes()
    report: dict[str, Any] = {
        "schema_version": 1,
        "kind": "deterministic_fault_recovery_soak",
        "status": "completed",
        "started_at": started_at,
        "finished_at": _now(),
        "iterations_requested": iterations,
        "iterations_completed": len(samples),
        "external_network_used": False,
        "paid_call_performed": False,
        "fault_injected": "kimi_http_503",
        "recovery_policy": "one manual retry",
        "downloads_total": sum(fixture.downloads.values()),
        "simulated_kimi_attempts_total": sum(fixture.kimi_attempts.values()),
        "temporary_media_files_after_each_recovery": 0,
        "memory_before_bytes": memory_before,
        "memory_after_bytes": memory_after,
        "max_working_set_bytes": max(
            [
                memory_before,
                memory_after,
                *[int(item["working_set_bytes"]) for item in samples],
            ]
        ),
        "samples": samples,
    }
    write_json(output, report)
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("build/fault-recovery-soak.json"),
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not 1 <= args.iterations <= 240:
        raise SystemExit("iterations must be between 1 and 240")
    report = _run(args.iterations, args.output.expanduser().resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
