"""Media validation and full-timeline Kimi proxy generation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .command import CommandRunner, run_command
from .config import Settings
from .errors import AppError


KIMI_FILE_LIMIT_BYTES = 95_000_000
KIMI_PROXY_TARGET_BYTES = 84_000_000


@dataclass(frozen=True)
class PreparedVideo:
    path: Path
    is_proxy: bool
    warnings: tuple[str, ...] = ()


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe_video(
    video_path: Path,
    *,
    runner: CommandRunner = run_command,
) -> dict[str, Any]:
    if not video_path.is_file() or video_path.stat().st_size <= 0:
        raise AppError("invalid_media", "下载文件不存在或为空。")
    result = runner(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(video_path),
        ],
        120,
    )
    if result.returncode != 0:
        raise AppError("invalid_media", "ffprobe 无法验证下载视频。")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AppError("invalid_media", "ffprobe 返回了无效 JSON。") from exc
    streams = payload.get("streams") if isinstance(payload, dict) else None
    if not isinstance(streams, list) or not any(
        isinstance(item, dict) and item.get("codec_type") == "video" for item in streams
    ):
        raise AppError("invalid_media", "下载文件不包含视频流。")
    has_audio = any(
        isinstance(item, dict) and item.get("codec_type") == "audio" for item in streams
    )
    video = next(item for item in streams if isinstance(item, dict) and item.get("codec_type") == "video")
    return {
        "size_bytes": video_path.stat().st_size,
        "has_video": True,
        "has_audio": has_audio,
        "video_codec": str(video.get("codec_name") or ""),
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
    }


def prepare_kimi_video(
    video_path: Path,
    *,
    duration_seconds: float,
    checkpoint_dir: Path,
    settings: Settings,
    runner: CommandRunner = run_command,
    file_limit_bytes: int = KIMI_FILE_LIMIT_BYTES,
    target_bytes: int = KIMI_PROXY_TARGET_BYTES,
) -> PreparedVideo:
    if not video_path.is_file() or video_path.stat().st_size <= 0:
        raise AppError("invalid_media", "Kimi 输入视频不存在或为空。")
    if video_path.stat().st_size <= file_limit_bytes:
        return PreparedVideo(video_path, False)
    if duration_seconds <= 0:
        raise AppError("kimi_proxy_failed", "无法确定视频时长，不能安全生成完整时间线代理。")

    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    proxy = checkpoint_dir / "kimi-proxy.mp4"
    attempts = [
        (target_bytes, 640, 360, 8, 48_000),
        (max(1_000_000, int(target_bytes * 0.83)), 480, 270, 5, 32_000),
    ]
    for attempt_target, width, height, fps, audio_bps in attempts:
        proxy.unlink(missing_ok=True)
        total_bps = max(128_000, int(attempt_target * 8 / duration_seconds * 0.94))
        video_bps = max(64_000, min(1_200_000, total_bps - audio_bps - 8_000))
        result = runner(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(video_path),
                "-map",
                "0:v:0",
                "-map",
                "0:a:0?",
                "-sn",
                "-dn",
                "-vf",
                (
                    f"scale={width}:{height}:force_original_aspect_ratio=decrease:"
                    f"force_divisible_by=2,fps={fps}"
                ),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-b:v",
                str(video_bps),
                "-maxrate",
                str(int(video_bps * 1.15)),
                "-bufsize",
                str(video_bps * 2),
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                str(audio_bps),
                "-ac",
                "1",
                "-movflags",
                "+faststart",
                str(proxy),
            ],
            settings.download_timeout_seconds,
        )
        if result.returncode == 0 and proxy.is_file() and 0 < proxy.stat().st_size <= file_limit_bytes:
            return PreparedVideo(
                proxy,
                True,
                (
                    "原视频超过 Kimi 单文件上限；已生成覆盖完整时间线的低码率分析代理。",
                ),
            )
    proxy.unlink(missing_ok=True)
    raise AppError(
        "kimi_proxy_failed",
        "无法把完整视频压缩到 Kimi 单文件上限以内；原视频未被修改。",
    )

