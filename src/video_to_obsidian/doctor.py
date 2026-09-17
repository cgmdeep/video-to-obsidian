"""Read-only environment diagnostics."""

from __future__ import annotations

import configparser
import importlib.util
import os
import platform
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import ConfigError, Settings, default_paths, load_settings
from .secrets import kimi_key_source


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    required: bool
    detail: str


def _application_exists(name: str) -> bool:
    if shutil.which(name):
        return True
    system = platform.system()
    if system == "Darwin":
        return (Path("/Applications") / f"{name}.app").exists()
    if system == "Windows":
        local = Path(os.environ.get("LOCALAPPDATA", ""))
        candidates = {
            "Obsidian": [local / "Programs/Obsidian/Obsidian.exe"],
            "Firefox": [
                Path(os.environ.get("PROGRAMFILES", "")) / "Mozilla Firefox/firefox.exe",
                Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Mozilla Firefox/firefox.exe",
            ],
        }
        return any(path.is_file() for path in candidates.get(name, []))
    return False


def _firefox_profiles_file() -> Path:
    system = platform.system()
    home = Path.home()
    if system == "Windows":
        root = Path(os.environ.get("APPDATA", home / "AppData/Roaming"))
        return root / "Mozilla/Firefox/profiles.ini"
    if system == "Darwin":
        return home / "Library/Application Support/Firefox/profiles.ini"
    return home / ".mozilla/firefox/profiles.ini"


def _firefox_profile_exists(name: str, *, profiles_file: Path | None = None) -> bool:
    path = profiles_file or _firefox_profiles_file()
    if not path.is_file():
        return False
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(path, encoding="utf-8")
    except (OSError, configparser.Error):
        return False
    expected = name.strip().casefold()
    return any(
        parser.get(section, "Name", fallback="").strip().casefold() == expected
        for section in parser.sections()
        if section.casefold().startswith("profile")
    )


def _vault_writable(settings: Settings) -> Check:
    vault = settings.vault_path.expanduser()
    ok = vault.is_dir() and os.access(vault, os.W_OK)
    return Check("vault", ok, True, f"Vault {'可写' if ok else '不存在或不可写'}：{vault}")


def run_doctor(config_path: Path | None = None) -> list[Check]:
    path = config_path or default_paths().config_file
    checks: list[Check] = []
    settings: Settings | None = None
    try:
        settings = load_settings(path)
        checks.append(Check("config", True, True, f"配置可读：{path}"))
    except ConfigError as exc:
        checks.append(Check("config", False, True, str(exc)))

    key_source = kimi_key_source()
    python_ok = sys.version_info >= (3, 11)
    yt_dlp_ok = importlib.util.find_spec("yt_dlp") is not None
    checks.extend(
        [
            Check(
                "python",
                python_ok,
                True,
                f"{platform.python_version()}（需要 3.11+）",
            ),
            Check("ffmpeg", shutil.which("ffmpeg") is not None, True, "已找到" if shutil.which("ffmpeg") else "未找到"),
            Check("ffprobe", shutil.which("ffprobe") is not None, True, "已找到" if shutil.which("ffprobe") else "未找到"),
            Check("yt-dlp", yt_dlp_ok, True, "Python 包已安装" if yt_dlp_ok else "Python 包未安装"),
            Check("firefox", _application_exists("Firefox"), True, "已安装" if _application_exists("Firefox") else "未找到"),
            Check("obsidian", _application_exists("Obsidian"), True, "已安装" if _application_exists("Obsidian") else "未找到"),
            Check(
                "kimi_key",
                key_source in {"environment", "keyring"},
                True,
                f"已配置（来源：{key_source}，值未显示）"
                if key_source in {"environment", "keyring"}
                else "未配置或系统钥匙串不可用",
            ),
        ]
    )
    if settings is not None:
        checks.append(_vault_writable(settings))
        profile_ok = _firefox_profile_exists(settings.firefox_profile)
        checks.append(
            Check(
                "firefox_profile",
                profile_ok,
                True,
                f"已找到专用 Profile：{settings.firefox_profile}"
                if profile_ok
                else f"未找到专用 Profile：{settings.firefox_profile}",
            )
        )
        transcript_ok = settings.transcript.mode == "off" or bool(os.environ.get("ASR_URL", "").strip())
        checks.append(
            Check(
                "transcript",
                transcript_ok,
                settings.transcript.required,
                "已关闭" if settings.transcript.mode == "off" else ("ASR 已配置" if transcript_ok else "ASR_URL 未配置"),
            )
        )
    return checks


def doctor_payload(config_path: Path | None = None) -> dict[str, object]:
    checks = run_doctor(config_path)
    required_ok = all(item.ok for item in checks if item.required)
    return {
        "ok": required_ok,
        "paid_call_performed": False,
        "checks": [asdict(item) for item in checks],
    }
