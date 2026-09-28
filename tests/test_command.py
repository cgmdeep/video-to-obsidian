import subprocess

import pytest

from video_to_obsidian.command import run_command, yt_dlp_command
from video_to_obsidian.errors import AppError


def test_ytdlp_timeout_has_safe_diagnostics_and_is_not_blindly_retryable(monkeypatch) -> None:
    class TimedOutProcess:
        returncode = 124

        def communicate(self, timeout=None):
            if timeout == 60:
                raise subprocess.TimeoutExpired("yt-dlp", timeout)
            return "", ""

        def kill(self):
            return None

    terminated = []
    monkeypatch.setattr(
        "video_to_obsidian.command._start_process",
        lambda command: (TimedOutProcess(), None),
    )
    monkeypatch.setattr(
        "video_to_obsidian.command._terminate_process_tree",
        lambda process, job: terminated.append(True),
    )

    with pytest.raises(AppError) as caught:
        run_command(yt_dlp_command("--version"), 60)

    assert caught.value.code == "command_timeout"
    assert caught.value.retryable is False
    assert caught.value.details["phase"] == "yt-dlp"
    assert caught.value.details["timeout_seconds"] == 60
    assert "python" not in caught.value.message.lower()
    assert terminated == [True]


def test_local_media_timeout_is_not_retryable(monkeypatch) -> None:
    class TimedOutProcess:
        returncode = 124

        def communicate(self, timeout=None):
            if timeout == 120:
                raise subprocess.TimeoutExpired("ffmpeg", timeout)
            return "", ""

        def kill(self):
            return None

    monkeypatch.setattr(
        "video_to_obsidian.command._start_process",
        lambda command: (TimedOutProcess(), None),
    )
    monkeypatch.setattr(
        "video_to_obsidian.command._terminate_process_tree",
        lambda process, job: None,
    )

    with pytest.raises(AppError) as caught:
        run_command(["ffmpeg", "-version"], 120)

    assert caught.value.code == "command_timeout"
    assert caught.value.retryable is False
    assert caught.value.details["phase"] == "ffmpeg"
