import json
from pathlib import Path

import pytest

from video_to_obsidian.command import CommandResult
from video_to_obsidian.config import initialize_settings, load_settings
from video_to_obsidian.errors import AppError
from video_to_obsidian.platforms.bilibili import (
    BilibiliMetadata,
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


def test_metadata_uses_resolved_dedicated_firefox_profile(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    profile = tmp_path / "real-profile"
    profile.mkdir()
    monkeypatch.setattr(
        "video_to_obsidian.platforms.bilibili.yt_dlp_cookie_spec",
        lambda _: f"firefox:{profile}",
    )
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
    assert f"firefox:{profile}" in captured["command"]


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

    def duplicate_runner(command: list[str], timeout: int) -> CommandResult:
        output = tmp_path / "download"
        output.mkdir(parents=True, exist_ok=True)
        (output / "source.mp4").write_bytes(b"one")
        (output / "source.webm").write_bytes(b"two")
        return CommandResult(0, "", "")

    with pytest.raises(AppError) as caught:
        download_video(resolved, metadata, tmp_path / "download", settings, runner=duplicate_runner)
    assert caught.value.code == "download_boundary_violation"


def test_http_412_uses_public_api_fallback(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    fallback = BilibiliMetadata(
        identity="bilibili_BV1Uw826pE7J_p01",
        bvid="BV1Uw826pE7J",
        part=1,
        url="https://www.bilibili.com/video/BV1Uw826pE7J",
        title="公开 API 标题",
        uploader="作者",
        uploader_id="1",
        duration=60,
        upload_date="20260928",
        description="",
        tags=("知识",),
        yt_dlp_id="BV1Uw826pE7J",
        download_auth="anonymous_public_api",
        avid="1",
        cid="2",
        download_strategy="public_api_412_fallback",
    )
    monkeypatch.setattr(
        "video_to_obsidian.platforms.bilibili._fetch_metadata_public_api",
        lambda resolved: fallback,
    )
    metadata = fetch_metadata(
        resolve_input("BV1Uw826pE7J"),
        settings,
        runner=lambda command, timeout: CommandResult(
            1, "", "HTTP Error 412: Precondition Failed"
        )
    )
    assert metadata.download_strategy == "public_api_412_fallback"
    assert metadata.cid == "2"


def test_metadata_timeout_uses_public_api_fallback(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    fallback = BilibiliMetadata(
        identity="bilibili_BV1Uw826pE7J_p01",
        bvid="BV1Uw826pE7J",
        part=1,
        url="https://www.bilibili.com/video/BV1Uw826pE7J",
        title="fallback",
        uploader="",
        uploader_id="",
        duration=60,
        upload_date="",
        description="",
        tags=(),
        yt_dlp_id="BV1Uw826pE7J",
        download_auth="anonymous_public_api",
        avid="1",
        cid="2",
        download_strategy="public_api_412_fallback",
    )
    monkeypatch.setattr(
        "video_to_obsidian.platforms.bilibili._fetch_metadata_public_api",
        lambda resolved: fallback,
    )

    def timeout(command, seconds):
        raise AppError("command_timeout", "timeout", details={"phase": "yt-dlp"})

    metadata = fetch_metadata(resolve_input("BV1Uw826pE7J"), settings, runner=timeout)
    assert metadata.identity == fallback.identity


def test_zero_file_download_uses_public_api_fallback(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    resolved = resolve_input("BV1Uw826pE7J")
    metadata = BilibiliMetadata(
        identity="bilibili_BV1Uw826pE7J_p01",
        bvid="BV1Uw826pE7J",
        part=1,
        url=resolved.canonical_url,
        title="x",
        uploader="",
        uploader_id="",
        duration=60,
        upload_date="",
        description="",
        tags=(),
        yt_dlp_id="BV1Uw826pE7J",
        download_auth="firefox_profile",
    )
    public_metadata = BilibiliMetadata(
        **{
            **metadata.__dict__,
            "download_auth": "anonymous_public_api",
            "cid": "2",
            "avid": "1",
            "download_strategy": "public_api_empty_download_fallback",
        }
    )
    monkeypatch.setattr(
        "video_to_obsidian.platforms.bilibili._fetch_metadata_public_api",
        lambda resolved: public_metadata,
    )

    def public_download(meta, output, cfg):
        path = output / "source.mp4"
        path.write_bytes(b"public-video")
        return path

    monkeypatch.setattr(
        "video_to_obsidian.platforms.bilibili._download_public_api_video",
        public_download,
    )
    path = download_video(
        resolved,
        metadata,
        tmp_path / "download",
        settings,
        runner=lambda command, timeout: CommandResult(0, "", ""),
    )
    assert path.read_bytes() == b"public-video"
