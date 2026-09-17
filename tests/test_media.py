import json
from pathlib import Path

import pytest

from video_to_obsidian.command import CommandResult
from video_to_obsidian.config import initialize_settings, load_settings
from video_to_obsidian.errors import AppError
from video_to_obsidian.media import prepare_kimi_video, probe_video


def _settings(tmp_path: Path):
    config = initialize_settings(
        tmp_path / "vault",
        config_path=tmp_path / "config.toml",
        runtime_root=tmp_path / "private",
    )
    return load_settings(config)


def test_probe_requires_video_stream(tmp_path: Path) -> None:
    media = tmp_path / "x.mp4"
    media.write_bytes(b"x")
    with pytest.raises(AppError) as caught:
        probe_video(
            media,
            runner=lambda command, timeout: CommandResult(
                0, json.dumps({"streams": [{"codec_type": "audio"}]}), ""
            ),
        )
    assert caught.value.code == "invalid_media"


def test_probe_reports_audio_and_dimensions(tmp_path: Path) -> None:
    media = tmp_path / "x.mp4"
    media.write_bytes(b"video")
    result = probe_video(
        media,
        runner=lambda command, timeout: CommandResult(
            0,
            json.dumps(
                {
                    "streams": [
                        {"codec_type": "video", "codec_name": "h264", "width": 1280, "height": 720},
                        {"codec_type": "audio", "codec_name": "aac"},
                    ]
                }
            ),
            "",
        ),
    )
    assert result["has_audio"] is True
    assert result["width"] == 1280


def test_small_video_is_used_directly(tmp_path: Path) -> None:
    media = tmp_path / "x.mp4"
    media.write_bytes(b"small")
    prepared = prepare_kimi_video(
        media,
        duration_seconds=60,
        checkpoint_dir=tmp_path / "checkpoint",
        settings=_settings(tmp_path),
        file_limit_bytes=100,
        target_bytes=80,
    )
    assert prepared.path == media
    assert prepared.is_proxy is False


def test_large_video_proxy_covers_full_timeline(tmp_path: Path) -> None:
    media = tmp_path / "x.mp4"
    media.write_bytes(b"x" * 101)
    commands = []

    def runner(command: list[str], timeout: int) -> CommandResult:
        commands.append(command)
        Path(command[-1]).write_bytes(b"p" * 90)
        return CommandResult(0, "", "")

    prepared = prepare_kimi_video(
        media,
        duration_seconds=120,
        checkpoint_dir=tmp_path / "checkpoint",
        settings=_settings(tmp_path),
        runner=runner,
        file_limit_bytes=100,
        target_bytes=90,
    )
    assert prepared.is_proxy is True
    assert prepared.path.stat().st_size == 90
    assert "-t" not in commands[0]
    assert "-ss" not in commands[0]
