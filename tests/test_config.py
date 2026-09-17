from pathlib import Path

import pytest

from video_to_obsidian.config import ConfigError, initialize_settings, load_settings


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
