import json
from pathlib import Path

import pytest

from video_to_obsidian.command import CommandResult
from video_to_obsidian.config import initialize_settings, load_settings
from video_to_obsidian.errors import AppError
from video_to_obsidian.platforms.douyin import download_video, fetch_metadata, resolve_input


def _settings(tmp_path: Path):
    config = initialize_settings(tmp_path / "vault", config_path=tmp_path / "config.toml")
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


def test_metadata_uses_dedicated_firefox_profile(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    captured = {}

    def runner(command: list[str], timeout: int) -> CommandResult:
        captured["command"] = command
        return CommandResult(
            0,
            json.dumps({"id": "1234567890123456789", "duration": 20}),
            "",
        )

    fetch_metadata(resolve_input("https://v.douyin.com/abc123/"), settings, runner=runner)
    assert "firefox:VideoToObsidian" in captured["command"]


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

