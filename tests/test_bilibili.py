import json
from pathlib import Path

import pytest

from video_to_obsidian.command import CommandResult
from video_to_obsidian.config import initialize_settings, load_settings
from video_to_obsidian.errors import AppError
from video_to_obsidian.platforms.bilibili import (
    download_video,
    fetch_metadata,
    resolve_input,
)


def _settings(tmp_path: Path):
    config = initialize_settings(tmp_path / "vault", config_path=tmp_path / "config.toml")
    return load_settings(config)


def test_resolve_share_text_and_part() -> None:
    resolved = resolve_input("微信分享 https://www.bilibili.com/video/BV1Uw826pE7J?p=2 认真看")
    assert resolved.bvid == "BV1Uw826pE7J"
    assert resolved.part == 2
    assert resolved.canonical_url.endswith("?p=2")


def test_resolve_b23_with_injected_redirect() -> None:
    resolved = resolve_input(
        "https://b23.tv/abc123",
        short_link_resolver=lambda _: "https://www.bilibili.com/video/BV1Uw826pE7J?p=3",
    )
    assert resolved.part == 3
    assert resolved.input_kind == "b23"


def test_metadata_uses_dedicated_firefox_profile(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    captured = {}

    def runner(command: list[str], timeout: int) -> CommandResult:
        captured["command"] = command
        payload = {
            "id": "BV1Uw826pE7J",
            "title": "测试视频",
            "uploader": "作者",
            "uploader_id": "1",
            "duration": 123,
            "upload_date": "20260917",
            "description": "描述",
            "tags": ["知识"],
        }
        return CommandResult(0, json.dumps(payload), "")

    metadata = fetch_metadata(resolve_input("BV1Uw826pE7J"), settings, runner=runner)
    assert metadata.identity == "bilibili_BV1Uw826pE7J_p01"
    assert "firefox:VideoToObsidian" in captured["command"]


def test_metadata_requires_explicit_part(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    def runner(command: list[str], timeout: int) -> CommandResult:
        return CommandResult(0, json.dumps({"_type": "playlist", "entries": [{}, {}]}), "")

    with pytest.raises(AppError) as caught:
        fetch_metadata(resolve_input("BV1Uw826pE7J"), settings, runner=runner)
    assert caught.value.code == "part_selection_required"


def test_download_requires_exactly_one_file(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    resolved = resolve_input("BV1Uw826pE7J")
    metadata = fetch_metadata(
        resolved,
        settings,
        runner=lambda command, timeout: CommandResult(
            0,
            json.dumps({"id": "BV1Uw826pE7J", "title": "x"}),
            "",
        ),
    )

    def empty_runner(command: list[str], timeout: int) -> CommandResult:
        return CommandResult(0, "", "")

    with pytest.raises(AppError) as caught:
        download_video(resolved, metadata, tmp_path / "download", settings, runner=empty_runner)
    assert caught.value.code == "download_boundary_violation"


def test_http_412_is_retryable(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    with pytest.raises(AppError) as caught:
        fetch_metadata(
            resolve_input("BV1Uw826pE7J"),
            settings,
            runner=lambda command, timeout: CommandResult(1, "", "HTTP Error 412: Precondition Failed"),
        )
    assert caught.value.code == "bilibili_request_blocked"
    assert caught.value.retryable is True

