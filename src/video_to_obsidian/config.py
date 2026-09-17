"""Cross-platform, secret-free application configuration."""

from __future__ import annotations

import json
import os
import platform
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Raised when public configuration is missing or invalid."""


@dataclass(frozen=True)
class AppPaths:
    config_file: Path
    cache: Path
    state: Path
    candidates: Path
    archive: Path


@dataclass(frozen=True)
class TranscriptSettings:
    mode: str = "off"
    required: bool = False


@dataclass(frozen=True)
class Settings:
    vault_path: Path
    preferences_file: Path
    profile: str
    save_video: bool
    default_model: str
    deep_model: str
    kimi_base_url: str
    vision_max_tokens: int
    deep_max_tokens: int
    download_timeout_seconds: int
    kimi_timeout_seconds: int
    firefox_profile: str
    transcript: TranscriptSettings
    paths: AppPaths


def default_paths() -> AppPaths:
    system = platform.system()
    home = Path.home()
    if system == "Windows":
        config_root = Path(os.environ.get("APPDATA", home / "AppData/Roaming")) / "VideoToObsidian"
        data_root = Path(os.environ.get("LOCALAPPDATA", home / "AppData/Local")) / "VideoToObsidian"
        cache_root = data_root / "cache"
    elif system == "Darwin":
        config_root = home / "Library/Application Support/VideoToObsidian"
        data_root = config_root
        cache_root = home / "Library/Caches/VideoToObsidian"
    else:
        config_root = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config")) / "video-to-obsidian"
        data_root = Path(os.environ.get("XDG_STATE_HOME", home / ".local/state")) / "video-to-obsidian"
        cache_root = Path(os.environ.get("XDG_CACHE_HOME", home / ".cache")) / "video-to-obsidian"
    return AppPaths(
        config_file=config_root / "config.toml",
        cache=cache_root,
        state=data_root / "state",
        candidates=data_root / "candidates",
        archive=data_root / "archive",
    )


def _required_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"配置项 {key} 必须是非空字符串。")
    return value.strip()


def _path_value(data: dict[str, Any], key: str, default: Path) -> Path:
    value = data.get(key)
    if value is None:
        return default
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"路径配置 {key} 必须是非空字符串。")
    return Path(value).expanduser()


def load_settings(config_path: Path | None = None) -> Settings:
    defaults = default_paths()
    path = (config_path or defaults.config_file).expanduser()
    if not path.is_file():
        raise ConfigError(f"配置文件不存在：{path}")
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"无法读取配置文件：{path}") from exc

    if data.get("schema_version") != 1:
        raise ConfigError("只支持 schema_version = 1。")
    profile = _required_string(data, "profile")
    if profile not in {"standard", "transcript"}:
        raise ConfigError("profile 只能是 standard 或 transcript。")

    transcript_data = data.get("transcript") or {}
    if not isinstance(transcript_data, dict):
        raise ConfigError("transcript 必须是 TOML 表。")
    transcript_mode = str(transcript_data.get("mode", "off")).strip().lower()
    if transcript_mode not in {"off", "local", "remote"}:
        raise ConfigError("transcript.mode 只能是 off、local 或 remote。")
    if profile == "standard" and transcript_mode != "off":
        raise ConfigError("standard 档位必须设置 transcript.mode = off。")

    path_data = data.get("paths") or {}
    if not isinstance(path_data, dict):
        raise ConfigError("paths 必须是 TOML 表。")
    app_paths = AppPaths(
        config_file=path,
        cache=_path_value(path_data, "cache", defaults.cache),
        state=_path_value(path_data, "state", defaults.state),
        candidates=_path_value(path_data, "candidates", defaults.candidates),
        archive=_path_value(path_data, "archive", defaults.archive),
    )
    return Settings(
        vault_path=Path(_required_string(data, "vault_path")).expanduser(),
        preferences_file=Path(
            str(data.get("preferences_file") or (path.parent / "summary-preferences.txt"))
        ).expanduser(),
        profile=profile,
        save_video=bool(data.get("save_video", False)),
        default_model=_required_string(data, "default_model"),
        deep_model=_required_string(data, "deep_model"),
        kimi_base_url=str(data.get("kimi_base_url", "https://api.moonshot.cn/v1")).strip().rstrip("/"),
        vision_max_tokens=int(data.get("vision_max_tokens", 16384)),
        deep_max_tokens=int(data.get("deep_max_tokens", 16000)),
        download_timeout_seconds=int(data.get("download_timeout_seconds", 1800)),
        kimi_timeout_seconds=int(data.get("kimi_timeout_seconds", 1200)),
        firefox_profile=_required_string(data, "firefox_profile"),
        transcript=TranscriptSettings(
            mode=transcript_mode,
            required=bool(transcript_data.get("required", False)),
        ),
        paths=app_paths,
    )


def _toml_string(value: str | Path) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def initialize_settings(
    vault_path: Path,
    *,
    profile: str = "standard",
    save_video: bool = False,
    config_path: Path | None = None,
    runtime_root: Path | None = None,
    overwrite: bool = False,
) -> Path:
    if profile not in {"standard", "transcript"}:
        raise ConfigError("profile 只能是 standard 或 transcript。")
    defaults = default_paths()
    target = (config_path or defaults.config_file).expanduser()
    if runtime_root is not None:
        private_root = runtime_root.expanduser().resolve()
        runtime_paths = AppPaths(
            config_file=target,
            cache=private_root / "cache",
            state=private_root / "state",
            candidates=private_root / "candidates",
            archive=private_root / "archive",
        )
    else:
        runtime_paths = defaults
    if target.exists() and not overwrite:
        raise ConfigError(f"配置文件已存在，拒绝覆盖：{target}")

    vault = vault_path.expanduser().resolve()
    vault.mkdir(parents=True, exist_ok=True)
    (vault / "Douyin").mkdir(exist_ok=True)
    (vault / "Bilibili").mkdir(exist_ok=True)
    for directory in (
        runtime_paths.cache,
        runtime_paths.state,
        runtime_paths.candidates,
        runtime_paths.archive,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    transcript_mode = "off" if profile == "standard" else "local"
    text = "\n".join(
        [
            "schema_version = 1",
            f"vault_path = {_toml_string(vault)}",
            f"preferences_file = {_toml_string(target.parent / 'summary-preferences.txt')}",
            f"profile = {_toml_string(profile)}",
            f"save_video = {'true' if save_video else 'false'}",
            'default_model = "kimi-k2.7-code"',
            'deep_model = "kimi-k3"',
            'kimi_base_url = "https://api.moonshot.cn/v1"',
            "vision_max_tokens = 16384",
            "deep_max_tokens = 16000",
            "download_timeout_seconds = 1800",
            "kimi_timeout_seconds = 1200",
            'firefox_profile = "VideoToObsidian"',
            "",
            "[transcript]",
            f"mode = {_toml_string(transcript_mode)}",
            "required = false",
            "",
            "[paths]",
            f"cache = {_toml_string(runtime_paths.cache)}",
            f"state = {_toml_string(runtime_paths.state)}",
            f"candidates = {_toml_string(runtime_paths.candidates)}",
            f"archive = {_toml_string(runtime_paths.archive)}",
            "",
        ]
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".config-", suffix=".toml", dir=target.parent)
    temp_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, target)
    finally:
        temp_path.unlink(missing_ok=True)
    return target
