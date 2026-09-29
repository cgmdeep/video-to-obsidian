from pathlib import Path

import pytest

from video_to_obsidian.config import (
    ConfigError,
    initialize_settings,
    load_settings,
    update_profile,
)


def test_initialize_standard_profile(tmp_path: Path) -> None:
    vault = tmp_path / "Video Knowledge Base"
    config = tmp_path / "private" / "config.toml"
    created = initialize_settings(vault, config_path=config, runtime_root=tmp_path / "private")
    settings = load_settings(created)
    assert settings.profile == "standard"
    assert settings.transcript.mode == "off"
    assert settings.save_video is False
    assert (vault / "Douyin").is_dir()
    assert (vault / "Bilibili").is_dir()
    assert not (vault / ".obsidian").exists()


def test_existing_config_is_not_overwritten(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    initialize_settings(
        tmp_path / "vault", config_path=config, runtime_root=tmp_path / "private"
    )
    original = config.read_bytes()
    with pytest.raises(ConfigError):
        initialize_settings(
            tmp_path / "other", config_path=config, runtime_root=tmp_path / "private"
        )
    assert config.read_bytes() == original


def test_existing_matching_config_can_be_reused_safely(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    config = tmp_path / "config.toml"
    initialize_settings(vault, config_path=config, runtime_root=tmp_path / "private")
    original = config.read_bytes()
    reused = initialize_settings(
        vault,
        config_path=config,
        runtime_root=tmp_path / "private",
        reuse_existing=True,
    )
    assert reused == config
    assert config.read_bytes() == original


def test_existing_different_config_is_not_reused(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    initialize_settings(
        tmp_path / "vault", config_path=config, runtime_root=tmp_path / "private"
    )
    with pytest.raises(ConfigError):
        initialize_settings(
            tmp_path / "other-vault",
            config_path=config,
            runtime_root=tmp_path / "private",
            reuse_existing=True,
        )


def test_transcript_profile_enables_local_mode(tmp_path: Path) -> None:
    config = initialize_settings(
        tmp_path / "vault",
        profile="transcript",
        config_path=tmp_path / "config.toml",
        runtime_root=tmp_path / "private",
    )
    assert load_settings(config).transcript.mode == "local"


def test_profile_can_switch_atomically_without_losing_other_settings(tmp_path: Path) -> None:
    config = initialize_settings(
        tmp_path / "vault",
        config_path=tmp_path / "config.toml",
        runtime_root=tmp_path / "private",
    )
    original_mode = config.stat().st_mode
    text = config.read_text(encoding="utf-8").replace(
        'deep_model = "kimi-k3"',
        'deep_model = "kimi-k3"\ncustom_future_key = "preserve-me"',
    )
    config.write_text(text, encoding="utf-8")

    path, changed = update_profile("transcript", config_path=config)
    settings = load_settings(path)
    assert changed is True
    assert settings.profile == "transcript"
    assert settings.transcript.mode == "local"
    assert 'custom_future_key = "preserve-me"' in path.read_text(encoding="utf-8")
    assert path.stat().st_mode == original_mode

    _, changed_again = update_profile("transcript", config_path=config)
    assert changed_again is False

    _, changed_back = update_profile("standard", config_path=config)
    standard = load_settings(config)
    assert changed_back is True
    assert standard.profile == "standard"
    assert standard.transcript.mode == "off"
