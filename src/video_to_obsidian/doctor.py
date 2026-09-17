"""Read-only environment diagnostics."""

from __future__ import annotations

import os
import platform
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import ConfigError, Settings, default_paths, load_settings


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

    checks.extend(
        [
            Check("python", True, True, platform.python_version()),
            Check("ffmpeg", shutil.which("ffmpeg") is not None, True, "已找到" if shutil.which("ffmpeg") else "未找到"),
            Check("ffprobe", shutil.which("ffprobe") is not None, True, "已找到" if shutil.which("ffprobe") else "未找到"),
            Check("yt-dlp", shutil.which("yt-dlp") is not None, True, "已找到" if shutil.which("yt-dlp") else "未找到"),
            Check("firefox", _application_exists("Firefox"), True, "已安装" if _application_exists("Firefox") else "未找到"),
            Check("obsidian", _application_exists("Obsidian"), True, "已安装" if _application_exists("Obsidian") else "未找到"),
            Check("kimi_key", bool(os.environ.get("KIMI_API_KEY", "").strip()), True, "已配置（值未显示）" if os.environ.get("KIMI_API_KEY", "").strip() else "未配置"),
        ]
    )
    if settings is not None:
        checks.append(_vault_writable(settings))
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

