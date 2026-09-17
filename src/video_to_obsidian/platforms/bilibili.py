"""Conservative Bilibili single-video adapter."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

import httpx

from ..command import CommandResult, CommandRunner, run_command, yt_dlp_command
from ..config import Settings
from ..errors import AppError


_SHORT_URL = re.compile(r"https://b23\.tv/[A-Za-z0-9]+", re.IGNORECASE)
_STANDARD_URL = re.compile(
    r"https?://(?:www\.)?bilibili\.com/video/(BV[0-9A-Za-z]{10})(?:/)?(?:\?[^\s]*)?",
    re.IGNORECASE,
)
_BV = re.compile(r"(?<![A-Za-z0-9])(BV[0-9A-Za-z]{10})(?![A-Za-z0-9])", re.IGNORECASE)
_ANY_BILIBILI_URL = re.compile(r"https?://(?:[^/]+\.)?bilibili\.com/", re.IGNORECASE)
_SAFE_ID = re.compile(r"[A-Za-z0-9._-]+")
_TRAILING = "，。；！？、,.!?;:：)）]】>》\"'"


@dataclass(frozen=True)
class ResolvedBilibili:
    bvid: str
    part: int | None
    canonical_url: str
    input_kind: str


@dataclass(frozen=True)
class BilibiliMetadata:
    identity: str
    bvid: str
    part: int
    url: str
    title: str
    uploader: str
    uploader_id: str
    duration: float
    upload_date: str
    description: str
    tags: tuple[str, ...]
    yt_dlp_id: str
    download_auth: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": "bilibili",
            "identity": self.identity,
            "bvid": self.bvid,
            "part": self.part,
            "url": self.url,
            "title": self.title,
            "uploader": self.uploader,
            "uploader_id": self.uploader_id,
            "duration": self.duration,
            "upload_date": self.upload_date,
            "description": self.description,
            "tags": list(self.tags),
            "yt_dlp_id": self.yt_dlp_id,
            "download_auth": self.download_auth,
        }


def _strip_url(value: str) -> str:
    return value.rstrip(_TRAILING)


def _canonical_from_url(url: str, input_kind: str) -> ResolvedBilibili:
    parsed = urlparse(_strip_url(url))
    if parsed.scheme not in {"http", "https"} or (parsed.hostname or "").lower() not in {
        "bilibili.com",
        "www.bilibili.com",
    }:
        raise AppError("unsupported_url", "只支持 bilibili.com 的普通 BV 视频链接。")
    match = re.fullmatch(r"/video/(BV[0-9A-Za-z]{10})/?", parsed.path, re.IGNORECASE)
    if not match:
        raise AppError(
            "unsupported_content",
            "只支持 B站普通 BV 单视频；番剧、直播、合集和空间页暂不支持。",
        )
    query = parse_qs(parsed.query)
    part: int | None = None
    if "p" in query:
        raw = query["p"][-1]
        if not re.fullmatch(r"[1-9]\d*", raw or ""):
            raise AppError("invalid_part", "分P参数 p 必须是大于0的整数。")
        part = int(raw)
    bvid = "BV" + match.group(1)[2:]
    canonical = f"https://www.bilibili.com/video/{bvid}"
    if part is not None:
        canonical += f"?p={part}"
    return ResolvedBilibili(bvid, part, canonical, input_kind)


def resolve_input(
    share_text: str,
    *,
    short_link_resolver: Callable[[str], str] | None = None,
) -> ResolvedBilibili:
    text = share_text or ""
    short = _SHORT_URL.search(text)
    if short:
        if short_link_resolver is None:
            short_link_resolver = resolve_short_link
        return _canonical_from_url(short_link_resolver(_strip_url(short.group(0))), "b23")
    standard = _STANDARD_URL.search(text)
    if standard:
        return _canonical_from_url(_strip_url(standard.group(0)), "standard_url")
    if _ANY_BILIBILI_URL.search(text):
        raise AppError(
            "unsupported_content",
            "只支持 B站普通 BV 单视频；番剧、直播、合集和空间页暂不支持。",
        )
    direct = _BV.search(text)
    if direct:
        bvid = "BV" + direct.group(1)[2:]
        return ResolvedBilibili(
            bvid,
            None,
            f"https://www.bilibili.com/video/{bvid}",
            "bvid",
        )
    raise AppError(
        "missing_video",
        "没有找到 B站单视频。请发送完整分享文本、b23.tv、标准 BV 链接或 BV 号。",
    )


def resolve_short_link(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() != "b23.tv":
        raise AppError("unsupported_url", "只允许解析 https://b23.tv/ 官方短链。")
    try:
        response = httpx.get(
            url,
            follow_redirects=True,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0 (video-to-obsidian/0.1)"},
        )
    except Exception as exc:
        raise AppError("short_link_failed", "B站短链解析失败。", retryable=True) from exc
    if response.status_code >= 400:
        raise AppError(
            "short_link_failed",
            f"B站短链解析失败：HTTP {response.status_code}。",
            retryable=response.status_code == 429 or response.status_code >= 500,
        )
    return str(response.url)


def _cookie_args(settings: Settings) -> list[str]:
    return ["--cookies-from-browser", f"firefox:{settings.firefox_profile}"]


def _classify_ytdlp(result: CommandResult) -> AppError:
    lowered = result.stderr.lower()
    if "http error 412" in lowered or "precondition failed" in lowered:
        return AppError(
            "bilibili_request_blocked",
            "B站拒绝了当前请求（HTTP 412），请稍后重试或重新扫码登录。",
            retryable=True,
            details={"http_status": 412},
        )
    if "http error 429" in lowered or "too many requests" in lowered:
        return AppError(
            "bilibili_rate_limited",
            "B站请求触发限流（HTTP 429）。",
            retryable=True,
            details={"http_status": 429},
        )
    if any(word in lowered for word in ("cookie", "login", "sign in", "会员", "登录")):
        return AppError(
            "bilibili_login_required",
            "B站登录态不可用，请用专用 Firefox Profile 重新扫码登录。",
        )
    return AppError(
        "yt_dlp_failed",
        "yt-dlp 处理 B站视频失败。请检查链接、地区限制和 yt-dlp 版本。",
    )


def fetch_metadata(
    resolved: ResolvedBilibili,
    settings: Settings,
    *,
    runner: CommandRunner = run_command,
) -> BilibiliMetadata:
    command = yt_dlp_command(
        "--ignore-config",
        "--no-warnings",
        "--skip-download",
        "--dump-single-json",
        "--no-playlist",
        *_cookie_args(settings),
        resolved.canonical_url,
    )
    result = runner(command, 180)
    if result.returncode != 0:
        raise _classify_ytdlp(result)
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AppError("invalid_metadata", "yt-dlp 返回了无效的B站元数据。") from exc
    if not isinstance(data, dict):
        raise AppError("invalid_metadata", "B站元数据不是对象。")
    result_type = str(data.get("_type") or "video")
    if result_type in {"playlist", "multi_video"}:
        entries = data.get("entries") if isinstance(data.get("entries"), list) else []
        if resolved.part is None:
            raise AppError(
                "part_selection_required",
                f"这是一个 {len(entries)} P 视频，请发送带 ?p=序号 的具体分P链接。",
                details={"part_count": len(entries)},
            )
        raise AppError(
            "unsupported_interactive_or_multi_video",
            "页面会展开多个媒体条目，已按单视频安全边界停止。",
        )
    yt_id = str(data.get("id") or "")
    match = re.fullmatch(r"(BV[0-9A-Za-z]{10})(?:_p([1-9]\d*))?", yt_id, re.IGNORECASE)
    if not match:
        raise AppError("invalid_metadata", "yt-dlp 没有返回稳定的 BV 单视频身份。")
    bvid = "BV" + match.group(1)[2:]
    if bvid.lower() != resolved.bvid.lower():
        raise AppError("identity_mismatch", "输入链接与 yt-dlp 返回的视频身份不一致。")
    part = int(match.group(2) or resolved.part or 1)
    if resolved.part is not None and part != resolved.part:
        raise AppError("identity_mismatch", "请求分P与实际返回分P不一致。")
    identity = f"bilibili_{bvid}_p{part:02d}"
    if not _SAFE_ID.fullmatch(identity):
        raise AppError("invalid_metadata", "无法生成安全的视频身份。")
    tags = tuple(str(item).strip() for item in (data.get("tags") or []) if str(item).strip())
    return BilibiliMetadata(
        identity=identity,
        bvid=bvid,
        part=part,
        url=resolved.canonical_url,
        title=str(data.get("title") or bvid),
        uploader=str(data.get("uploader") or ""),
        uploader_id=str(data.get("uploader_id") or ""),
        duration=float(data.get("duration") or 0),
        upload_date=str(data.get("upload_date") or ""),
        description=str(data.get("description") or ""),
        tags=tags,
        yt_dlp_id=yt_id,
        download_auth="firefox_profile",
    )


def download_video(
    resolved: ResolvedBilibili,
    metadata: BilibiliMetadata,
    output_dir: Path,
    settings: Settings,
    *,
    runner: CommandRunner = run_command,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    template = output_dir / "source.%(ext)s"
    command = yt_dlp_command(
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
        resolved.canonical_url,
    )
    result = runner(command, settings.download_timeout_seconds)
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
    if metadata.identity != f"bilibili_{resolved.bvid}_p{metadata.part:02d}":
        raise AppError("identity_mismatch", "下载前后的稳定身份不一致。")
    return path
