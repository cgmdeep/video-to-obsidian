"""Conservative Douyin single-video adapter using the user's Firefox login."""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from ..command import CommandResult, CommandRunner, run_command, yt_dlp_command
from ..config import Settings
from ..errors import AppError
from ..firefox import yt_dlp_cookie_spec


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


@dataclass(frozen=True)
class _BrowserCapture:
    source_url: str
    page_url: str
    media_urls: tuple[str, ...]
    user_agent: str
    title: str
    description: str
    uploader: str


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
    return ["--cookies-from-browser", yt_dlp_cookie_spec(settings.firefox_profile)]


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


def _allowed_media_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    return any(
        host == suffix or host.endswith(f".{suffix}")
        for suffix in ("douyinvod.com", "bytecdn.cn", "bytecdn.com")
    )


def _probe_streams(path: Path, *, runner: CommandRunner = run_command) -> dict[str, Any]:
    result = runner(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ],
        120,
    )
    if result.returncode != 0:
        return {}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    streams = payload.get("streams") if isinstance(payload, dict) else None
    if not isinstance(streams, list):
        return {}
    return {
        "has_video": any(
            isinstance(item, dict) and item.get("codec_type") == "video"
            for item in streams
        ),
        "has_audio": any(
            isinstance(item, dict) and item.get("codec_type") == "audio"
            for item in streams
        ),
    }


class DouyinDownloadAdapter:
    """Use yt-dlp when possible, then fall back to the user's real Firefox session."""

    def __init__(self) -> None:
        self._capture: _BrowserCapture | None = None
        self._use_ytdlp = False

    def metadata(self, resolved: ResolvedDouyin, settings: Settings) -> DouyinMetadata:
        try:
            metadata = fetch_metadata(resolved, settings)
        except AppError as exc:
            if exc.code not in {"douyin_login_required", "yt_dlp_failed"}:
                raise
            capture = self._capture_browser(resolved, settings)
            self._capture = capture
            self._use_ytdlp = False
            match = re.search(r"/video/(\d{8,30})", capture.page_url)
            if not match:
                raise AppError("invalid_metadata", "无法从抖音链接取得稳定作品 ID。")
            aweme_id = match.group(1)
            title = re.sub(r"\s*[-|_]\s*抖音.*$", "", capture.title).strip()
            if not title:
                title = capture.description.strip()[:120] or aweme_id
            return DouyinMetadata(
                identity=f"douyin_{aweme_id}",
                aweme_id=aweme_id,
                url=f"https://www.douyin.com/video/{aweme_id}",
                title=title,
                uploader=capture.uploader,
                uploader_id="",
                duration=0,
                upload_date="",
                description=capture.description,
                tags=(),
                download_auth="firefox_browser",
            )
        self._capture = None
        self._use_ytdlp = True
        return metadata

    def download(
        self,
        resolved: ResolvedDouyin,
        metadata: DouyinMetadata,
        output_dir: Path,
        settings: Settings,
    ) -> Path:
        if self._use_ytdlp:
            return download_video(resolved, metadata, output_dir, settings)
        capture = self._capture
        self._capture = None
        if capture is None or capture.source_url != resolved.url:
            raise AppError(
                "douyin_browser_capture_missing",
                "抖音浏览器下载上下文已失效，请重新提交该视频。",
            )
        return self._download_browser_capture(capture, output_dir, settings)

    def _capture_browser(
        self,
        resolved: ResolvedDouyin,
        settings: Settings,
    ) -> _BrowserCapture:
        try:
            from selenium import webdriver
            from selenium.webdriver.firefox.options import Options
        except ImportError as exc:
            raise AppError(
                "missing_dependency",
                "抖音浏览器下载需要 Selenium；请重新运行安装器修复运行环境。",
            ) from exc

        from ..firefox import resolve_profile_directory

        profile = resolve_profile_directory(settings.firefox_profile)
        if profile is None or not profile.is_dir():
            raise AppError(
                "douyin_login_required",
                "找不到专用 Firefox Profile，请重新运行安装器并扫码登录抖音。",
            )

        options = Options()
        options.add_argument("-headless")
        options.profile = str(profile)
        options.set_preference("media.autoplay.default", 0)
        options.set_preference("media.autoplay.blocking_policy", 0)
        driver = None
        try:
            driver = webdriver.Firefox(options=options)
            driver.set_page_load_timeout(90)
            driver.get(resolved.url)
            deadline = time.monotonic() + 45
            first_media_at: float | None = None
            resources: list[dict[str, Any]] = []
            while time.monotonic() < deadline:
                raw = driver.execute_script(
                    """
                    return performance.getEntriesByType('resource').map(r => ({
                      name: r.name || '',
                      transferSize: r.transferSize || 0
                    }));
                    """
                )
                resources = raw if isinstance(raw, list) else []
                captured_urls = {
                    str(item.get("name") or "")
                    for item in resources
                    if _allowed_media_url(str(item.get("name") or ""))
                }
                if captured_urls and first_media_at is None:
                    first_media_at = time.monotonic()
                if len(captured_urls) >= 2:
                    break
                if first_media_at is not None and time.monotonic() - first_media_at >= 15:
                    break
                time.sleep(1)

            ranked = sorted(
                (
                    (int(item.get("transferSize") or 0), str(item.get("name") or ""))
                    for item in resources
                    if _allowed_media_url(str(item.get("name") or ""))
                ),
                reverse=True,
            )
            media_urls = tuple(dict.fromkeys(url for _, url in ranked if url))
            if not media_urls:
                raise AppError(
                    "douyin_browser_capture_failed",
                    "Firefox 已打开抖音页面，但没有捕获到单视频媒体请求。",
                )
            metadata = driver.execute_script(
                """
                const pick = (...selectors) => {
                  for (const selector of selectors) {
                    const node = document.querySelector(selector);
                    if (node && node.content) return node.content;
                  }
                  return '';
                };
                return {
                  title: document.title || pick('meta[property="og:title"]'),
                  description: pick('meta[name="description"]', 'meta[property="og:description"]'),
                  uploader: pick('meta[name="author"]')
                };
                """
            )
            return _BrowserCapture(
                source_url=resolved.url,
                page_url=str(driver.current_url),
                media_urls=media_urls,
                user_agent=str(driver.execute_script("return navigator.userAgent") or ""),
                title=str((metadata or {}).get("title") or ""),
                description=str((metadata or {}).get("description") or ""),
                uploader=str((metadata or {}).get("uploader") or ""),
            )
        except AppError:
            raise
        except Exception as exc:
            raise AppError(
                "douyin_browser_failed",
                "Firefox 自动读取抖音视频失败；请关闭专用 Firefox 后重试。",
            ) from exc
        finally:
            if driver is not None:
                driver.quit()

    def _download_browser_capture(
        self,
        capture: _BrowserCapture,
        output_dir: Path,
        settings: Settings,
    ) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        destination = output_dir / "source.mp4"
        with tempfile.TemporaryDirectory(prefix="douyin-browser-", dir=output_dir) as temporary:
            temp_dir = Path(temporary)
            video_source: Path | None = None
            audio_source: Path | None = None
            combined_source: Path | None = None
            timeout = httpx.Timeout(float(settings.download_timeout_seconds))
            with httpx.Client(follow_redirects=True, timeout=timeout) as client:
                for index, media_url in enumerate(capture.media_urls[:8]):
                    if not _allowed_media_url(media_url):
                        continue
                    candidate = temp_dir / f"candidate-{index}.media"
                    try:
                        with client.stream(
                            "GET",
                            media_url,
                            headers={
                                "User-Agent": capture.user_agent,
                                "Referer": capture.page_url,
                            },
                        ) as response:
                            if response.status_code not in {200, 206}:
                                continue
                            with candidate.open("wb") as handle:
                                for chunk in response.iter_bytes():
                                    handle.write(chunk)
                        if candidate.stat().st_size < 100_000:
                            continue
                        probe = _probe_streams(candidate)
                        if probe.get("has_video") and probe.get("has_audio"):
                            combined_source = candidate
                            break
                        if probe.get("has_video") and (
                            video_source is None
                            or candidate.stat().st_size > video_source.stat().st_size
                        ):
                            video_source = candidate
                        if probe.get("has_audio") and (
                            audio_source is None
                            or candidate.stat().st_size > audio_source.stat().st_size
                        ):
                            audio_source = candidate
                    except (OSError, httpx.HTTPError):
                        candidate.unlink(missing_ok=True)

            if combined_source is not None:
                os.replace(combined_source, destination)
            elif video_source is not None and audio_source is not None:
                result = run_command(
                    [
                        "ffmpeg",
                        "-y",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-i",
                        str(video_source),
                        "-i",
                        str(audio_source),
                        "-map",
                        "0:v:0",
                        "-map",
                        "1:a:0",
                        "-c",
                        "copy",
                        str(destination),
                    ],
                    settings.download_timeout_seconds,
                )
                if result.returncode != 0:
                    destination.unlink(missing_ok=True)
                    raise AppError(
                        "douyin_media_merge_failed",
                        "抖音音视频流下载成功，但 ffmpeg 合并失败。",
                    )
            else:
                raise AppError(
                    "douyin_media_incomplete",
                    "浏览器已捕获抖音媒体，但未同时取得完整画面和声音。",
                )
        if not destination.is_file() or destination.stat().st_size <= 0:
            raise AppError("download_boundary_violation", "抖音浏览器下载没有产生单个媒体文件。")
        return destination
