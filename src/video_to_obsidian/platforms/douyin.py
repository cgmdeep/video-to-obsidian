"""Conservative Douyin single-video adapter using the user's Firefox login."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..command import CommandResult, CommandRunner, run_command, yt_dlp_command
from ..config import Settings
from ..errors import AppError


_URL = re.compile(
    r"https?://(?:(?:www\.)?douyin\.com/video/\d+|v\.douyin\.com/[A-Za-z0-9_-]+)(?:/)?(?:\?[^\s]*)?",
    re.IGNORECASE,
)
_SAFE_ID = re.compile(r"[A-Za-z0-9._-]+")
_TRAILING = "，。；！？、,.!?;:：)）]】>》\"'"


@dataclass(frozen=True)
class ResolvedDouyin:
    url: str
    input_kind: str


@dataclass(frozen=True)
class DouyinMetadata:
    identity: str
    aweme_id: str
    url: str
    title: str
    uploader: str
    uploader_id: str
    duration: float
    upload_date: str
    description: str
    tags: tuple[str, ...]
    download_auth: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": "douyin",
            "identity": self.identity,
            "aweme_id": self.aweme_id,
            "url": self.url,
            "title": self.title,
            "uploader": self.uploader,
            "uploader_id": self.uploader_id,
            "duration": self.duration,
            "upload_date": self.upload_date,
            "description": self.description,
            "tags": list(self.tags),
            "download_auth": self.download_auth,
        }


def resolve_input(share_text: str) -> ResolvedDouyin:
    match = _URL.search(share_text or "")
    if not match:
        raise AppError(
            "missing_video",
            "没有找到抖音单视频链接。请发送包含 v.douyin.com 或 douyin.com/video/ 的完整分享文本。",
        )
    url = match.group(0).rstrip(_TRAILING)
    kind = "short_url" if "v.douyin.com" in url.lower() else "standard_url"
    return ResolvedDouyin(url, kind)


def _cookie_args(settings: Settings) -> list[str]:
    return ["--cookies-from-browser", f"firefox:{settings.firefox_profile}"]


def _classify_ytdlp(result: CommandResult) -> AppError:
    lowered = result.stderr.lower()
    if "http error 429" in lowered or "too many requests" in lowered:
        return AppError(
            "douyin_rate_limited",
            "抖音请求触发限流（HTTP 429）。",
            retryable=True,
            details={"http_status": 429},
        )
    if "http error 5" in lowered:
        return AppError(
            "douyin_upstream_failed",
            "抖音上游暂时不可用。",
            retryable=True,
        )
    if any(word in lowered for word in ("cookie", "login", "fresh cookies", "登录")):
        return AppError(
            "douyin_login_required",
            "抖音登录态不可用，请用专用 Firefox Profile 重新扫码登录。",
        )
    if "unsupported url" in lowered:
        return AppError("unsupported_content", "该链接不是受支持的抖音单视频。")
    return AppError(
        "yt_dlp_failed",
        "yt-dlp 处理抖音视频失败。请检查登录态、链接可用性和 yt-dlp 版本。",
    )


def fetch_metadata(
    resolved: ResolvedDouyin,
    settings: Settings,
    *,
    runner: CommandRunner = run_command,
) -> DouyinMetadata:
    result = runner(
        yt_dlp_command(
            "--ignore-config",
            "--no-warnings",
            "--skip-download",
            "--dump-single-json",
            "--no-playlist",
            *_cookie_args(settings),
            resolved.url,
        ),
        180,
    )
    if result.returncode != 0:
        raise _classify_ytdlp(result)
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AppError("invalid_metadata", "yt-dlp 返回了无效的抖音元数据。") from exc
    if not isinstance(data, dict):
        raise AppError("invalid_metadata", "抖音元数据不是对象。")
    if str(data.get("_type") or "video") in {"playlist", "multi_video"}:
        raise AppError(
            "unsupported_multi_video",
            "该页面会展开多个媒体条目，已按单视频安全边界停止。",
        )
    aweme_id = str(data.get("id") or "").strip()
    if not re.fullmatch(r"\d{8,30}", aweme_id):
        raise AppError("invalid_metadata", "yt-dlp 没有返回稳定的抖音作品 ID。")
    identity = f"douyin_{aweme_id}"
    if not _SAFE_ID.fullmatch(identity):
        raise AppError("invalid_metadata", "无法生成安全的抖音视频身份。")
    duration = float(data.get("duration") or 0)
    if duration <= 0:
        raise AppError("unsupported_content", "当前作品不是可验证的普通视频。")
    tags = tuple(str(item).strip() for item in (data.get("tags") or []) if str(item).strip())
    return DouyinMetadata(
        identity=identity,
        aweme_id=aweme_id,
        url=str(data.get("webpage_url") or resolved.url),
        title=str(data.get("title") or data.get("description") or aweme_id),
        uploader=str(data.get("uploader") or ""),
        uploader_id=str(data.get("uploader_id") or ""),
        duration=duration,
        upload_date=str(data.get("upload_date") or ""),
        description=str(data.get("description") or ""),
        tags=tags,
        download_auth="firefox_profile",
    )


def download_video(
    resolved: ResolvedDouyin,
    metadata: DouyinMetadata,
    output_dir: Path,
    settings: Settings,
    *,
    runner: CommandRunner = run_command,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    template = output_dir / "source.%(ext)s"
    result = runner(
        yt_dlp_command(
            "--ignore-config",
            "--no-warnings",
            "--no-playlist",
            "--format",
            "bv*+ba/b",
            "--merge-output-format",
            "mp4",
            "--print",
            "after_move:filepath",
            "--output",
            str(template),
            *_cookie_args(settings),
            resolved.url,
        ),
        settings.download_timeout_seconds,
    )
    if result.returncode != 0:
        raise _classify_ytdlp(result)
    candidates = [path for path in output_dir.glob("source.*") if path.is_file() and path.stat().st_size > 0]
    if len(candidates) != 1:
        raise AppError(
            "download_boundary_violation",
            f"下载阶段产生 {len(candidates)} 个媒体文件，为避免隐式批量处理已停止。",
        )
    path = candidates[0]
    reported = [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()]
    if reported and path.resolve() not in {item.expanduser().resolve() for item in reported}:
        raise AppError("identity_mismatch", "yt-dlp 报告的下载路径与实际单文件不一致。")
    if metadata.identity != f"douyin_{metadata.aweme_id}":
        raise AppError("identity_mismatch", "下载前后的稳定身份不一致。")
    return path
