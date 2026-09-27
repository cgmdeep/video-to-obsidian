"""Resolve a configured Firefox profile name to its real on-disk directory."""

from __future__ import annotations

import configparser
import os
import platform
from pathlib import Path


def profiles_file() -> Path:
    system = platform.system()
    home = Path.home()
    if system == "Windows":
        root = Path(os.environ.get("APPDATA", home / "AppData/Roaming"))
        return root / "Mozilla/Firefox/profiles.ini"
    if system == "Darwin":
        return home / "Library/Application Support/Firefox/profiles.ini"
    return home / ".mozilla/firefox/profiles.ini"


def resolve_profile_directory(
    name_or_path: str,
    *,
    profiles_ini: Path | None = None,
) -> Path | None:
    """Return the actual Firefox profile directory for a display name or path."""

    configured = Path(name_or_path).expanduser()
    if configured.is_dir():
        return configured.resolve()

    ini = profiles_ini or profiles_file()
    if not ini.is_file():
        return None
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(ini, encoding="utf-8")
    except (OSError, configparser.Error):
        return None

    expected = name_or_path.strip().casefold()
    for section in parser.sections():
        if not section.casefold().startswith("profile"):
            continue
        if parser.get(section, "Name", fallback="").strip().casefold() != expected:
            continue
        raw_path = parser.get(section, "Path", fallback="").strip()
        if not raw_path:
            return None
        candidate = Path(raw_path)
        if parser.getboolean(section, "IsRelative", fallback=True):
            candidate = ini.parent / candidate
        return candidate.expanduser().resolve()
    return None


def profile_exists(name_or_path: str, *, profiles_ini: Path | None = None) -> bool:
    resolved = resolve_profile_directory(name_or_path, profiles_ini=profiles_ini)
    return bool(resolved and resolved.is_dir())


def yt_dlp_cookie_spec(name_or_path: str) -> str:
    resolved = resolve_profile_directory(name_or_path)
    if resolved is None or not resolved.is_dir():
        # Keep the configured value so yt-dlp emits its normal actionable error.
        return f"firefox:{name_or_path}"
    return f"firefox:{resolved}"
