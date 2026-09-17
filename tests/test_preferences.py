from pathlib import Path

import pytest

from video_to_obsidian.config import initialize_settings, load_settings
from video_to_obsidian.preferences import (
    PreferenceError,
    clear_preferences,
    effective_instruction,
    read_preferences,
    write_preferences,
)


def _settings(tmp_path: Path):
    config = initialize_settings(
        tmp_path / "vault",
        config_path=tmp_path / "private/config.toml",
        runtime_root=tmp_path / "private/runtime",
    )
    return load_settings(config)


def test_preferences_live_outside_vault_and_are_combined(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    path = write_preferences(settings, "按时间线详细总结，注意反讽")
    assert settings.vault_path not in path.parents
    assert read_preferences(settings) == "按时间线详细总结，注意反讽"
    combined, character_count = effective_instruction(settings, "本次重点保留数据")
    assert "长期总结偏好" in combined
    assert "按时间线详细总结，注意反讽" in combined
    assert "本次视频要求" in combined
    assert "本次重点保留数据" in combined
    assert character_count > 0


def test_clear_preferences_restores_default(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    write_preferences(settings, "简洁")
    assert clear_preferences(settings) is True
    assert clear_preferences(settings) is False
    assert read_preferences(settings) == ""


def test_empty_preferences_are_rejected(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    with pytest.raises(PreferenceError):
        write_preferences(settings, "   ")
