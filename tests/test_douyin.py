import json
from pathlib import Path

import pytest

from video_to_obsidian.command import CommandResult
from video_to_obsidian.config import initialize_settings, load_settings
from video_to_obsidian.errors import AppError
from video_to_obsidian.platforms.douyin import (
    DouyinDownloadAdapter,
    _BrowserCapture,
    _allowed_media_url,
    _browser_requires_human_verification,
    download_video,
    fetch_metadata,
    resolve_input,
)


def _settings(tmp_path: Path):
    config = initialize_settings(
        tmp_path / "vault",
        config_path=tmp_path / "config.toml",
        runtime_root=tmp_path / "private",
    )
    return load_settings(config)


def test_resolves_full_share_text() -> None:
    result = resolve_input("6.52 复制打开抖音 https://v.douyin.com/Abc_123/ 看视频")
    assert result.url == "https://v.douyin.com/Abc_123/"
    assert result.input_kind == "short_url"


def test_metadata_requires_stable_video_id_and_duration(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    metadata = fetch_metadata(
        resolve_input("https://www.douyin.com/video/1234567890123456789"),
        settings,
        runner=lambda command, timeout: CommandResult(
            0,
            json.dumps(
                {
                    "id": "1234567890123456789",
                    "title": "测试抖音",
                    "duration": 30,
                    "uploader": "作者",
                    "upload_date": "20260917",
                }
            ),
            "",
        ),
    )
    assert metadata.identity == "douyin_1234567890123456789"
    assert metadata.duration == 30


def test_official_share_text_repairs_title_and_numeric_author(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    resolved = resolve_input(
        "【清醒博主的作品】 这是反讽测试 #知识 #测试 "
        "https://www.douyin.com/video/1234567890123456789"
    )
    metadata = fetch_metadata(
        resolved,
        settings,
        runner=lambda command, timeout: CommandResult(
            0,
            json.dumps(
                {
                    "id": "1234567890123456789",
                    "title": "页面重复标题",
                    "duration": 30,
                    "uploader": "123456",
                }
            ),
            "",
        ),
    )
    assert metadata.title == "这是反讽测试"
    assert metadata.uploader == "清醒博主"


def test_browser_human_verification_detection() -> None:
    class Driver:
        def execute_script(self, script):
            return True

    assert _browser_requires_human_verification(Driver()) is True


def test_metadata_uses_resolved_dedicated_firefox_profile(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    profile = tmp_path / "real-profile"
    profile.mkdir()
    monkeypatch.setattr(
        "video_to_obsidian.platforms.douyin.yt_dlp_cookie_spec",
        lambda _: f"firefox:{profile}",
    )
    captured = {}

    def runner(command: list[str], timeout: int) -> CommandResult:
        captured["command"] = command
        captured["timeout"] = timeout
        return CommandResult(
            0,
            json.dumps({"id": "1234567890123456789", "duration": 20}),
            "",
        )

    fetch_metadata(resolve_input("https://v.douyin.com/abc123/"), settings, runner=runner)
    assert f"firefox:{profile}" in captured["command"]
    assert captured["timeout"] == 120


def test_rejects_non_video_item(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    with pytest.raises(AppError) as caught:
        fetch_metadata(
            resolve_input("https://v.douyin.com/abc123/"),
            settings,
            runner=lambda command, timeout: CommandResult(
                0, json.dumps({"id": "1234567890123456789", "duration": 0}), ""
            ),
        )
    assert caught.value.code == "unsupported_content"


def test_download_zero_files_is_stopped(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    resolved = resolve_input("https://v.douyin.com/abc123/")
    metadata = fetch_metadata(
        resolved,
        settings,
        runner=lambda command, timeout: CommandResult(
            0, json.dumps({"id": "1234567890123456789", "duration": 20}), ""
        ),
    )
    with pytest.raises(AppError) as caught:
        download_video(
            resolved,
            metadata,
            tmp_path / "download",
            settings,
            runner=lambda command, timeout: CommandResult(0, "", ""),
        )
    assert caught.value.code == "download_boundary_violation"


def test_browser_media_allowlist_rejects_lookalike_hosts() -> None:
    assert _allowed_media_url("https://v26-webf.douyinvod.com/path") is True
    assert _allowed_media_url("http://v26-webf.douyinvod.com/path") is False
    assert _allowed_media_url("https://douyinvod.com.evil.example/path") is False


def test_adapter_falls_back_to_browser_without_persisting_media_url(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = _settings(tmp_path)
    adapter = DouyinDownloadAdapter()
    resolved = resolve_input("https://v.douyin.com/abc123/")
    capture = _BrowserCapture(
        source_url=resolved.url,
        page_url="https://www.douyin.com/video/1234567890123456789",
        media_urls=("https://v26-webf.douyinvod.com/signed",),
        user_agent="Mozilla/5.0",
        title="测试标题 - 抖音",
        description="测试描述",
        uploader="测试作者",
    )

    def fail_ytdlp(*args, **kwargs):
        raise AppError("douyin_login_required", "fresh cookies")

    monkeypatch.setattr("video_to_obsidian.platforms.douyin.fetch_metadata", fail_ytdlp)
    monkeypatch.setattr(adapter, "_capture_browser", lambda *_: capture)
    metadata = adapter.metadata(resolved, settings)

    assert metadata.identity == "douyin_1234567890123456789"
    assert metadata.url == "https://www.douyin.com/video/1234567890123456789"
    assert metadata.title == "测试标题"
    assert metadata.download_auth == "firefox_browser"
    assert "signed" not in json.dumps(metadata.to_dict(), ensure_ascii=False)


def test_adapter_falls_back_to_browser_when_metadata_command_times_out(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = _settings(tmp_path)
    adapter = DouyinDownloadAdapter()
    resolved = resolve_input("https://v.douyin.com/abc123/")
    capture = _BrowserCapture(
        source_url=resolved.url,
        page_url="https://www.douyin.com/video/1234567890123456789",
        media_urls=("https://v26-webf.douyinvod.com/signed",),
        user_agent="Mozilla/5.0",
        title="超时后回退 - 抖音",
        description="测试描述",
        uploader="测试作者",
    )

    def timeout_ytdlp(*args, **kwargs):
        raise AppError(
            "command_timeout",
            "yt-dlp 执行超过 120 秒，已停止。",
            retryable=True,
            details={"phase": "yt-dlp", "timeout_seconds": 120},
        )

    monkeypatch.setattr("video_to_obsidian.platforms.douyin.fetch_metadata", timeout_ytdlp)
    monkeypatch.setattr(adapter, "_capture_browser", lambda *_: capture)

    metadata = adapter.metadata(resolved, settings)

    assert metadata.identity == "douyin_1234567890123456789"
    assert metadata.download_auth == "firefox_browser"
