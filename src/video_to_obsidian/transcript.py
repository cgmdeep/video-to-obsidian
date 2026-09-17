"""Optional SenseVoice-compatible transcription; standard mode never calls it."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import httpx

from .command import CommandRunner, run_command
from .config import Settings
from .errors import AppError


@dataclass(frozen=True)
class TranscriptResult:
    text: str
    audio_bytes: int


def transcribe_video(
    video_path: Path,
    settings: Settings,
    *,
    runner: CommandRunner = run_command,
) -> TranscriptResult:
    if settings.transcript.mode == "off":
        return TranscriptResult("", 0)
    asr_url = os.environ.get("ASR_URL", "").strip()
    if not asr_url and settings.transcript.mode == "local":
        asr_url = "http://127.0.0.1:8010/v1/audio/transcriptions"
    if not asr_url:
        raise AppError("asr_unavailable", "逐字稿增强版尚未配置 ASR_URL。")
    with tempfile.TemporaryDirectory(prefix="video-to-obsidian-asr-") as temporary:
        wav = Path(temporary) / "audio.wav"
        result = runner(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(video_path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(wav),
            ],
            settings.download_timeout_seconds,
        )
        if result.returncode != 0 or not wav.is_file() or wav.stat().st_size <= 0:
            raise AppError("audio_extract_failed", "无法从视频提取 SenseVoice 音频。")
        audio_bytes = wav.stat().st_size
        headers = {}
        token = os.environ.get("ASR_TOKEN", "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            with wav.open("rb") as handle, httpx.Client(timeout=900) as client:
                response = client.post(
                    asr_url,
                    headers=headers,
                    files={"file": ("audio.wav", handle, "audio/wav")},
                )
        except Exception as exc:
            raise AppError("asr_failed", "连接 SenseVoice 失败。", retryable=True) from exc
        if response.status_code in {401, 403}:
            raise AppError("asr_auth_failed", "SenseVoice 鉴权失败。")
        if response.status_code != 200:
            raise AppError(
                "asr_failed",
                f"SenseVoice 返回 HTTP {response.status_code}。",
                retryable=response.status_code == 429 or response.status_code >= 500,
            )
        try:
            payload = response.json()
            text = str(payload.get("text") or "").strip()
        except (TypeError, ValueError) as exc:
            raise AppError("asr_failed", "SenseVoice 返回结构无效。") from exc
        if not text:
            raise AppError("asr_empty", "SenseVoice 没有返回逐字稿。")
        return TranscriptResult(text, audio_bytes)

