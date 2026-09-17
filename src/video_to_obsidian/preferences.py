"""Private, user-controlled summary preferences."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .config import Settings


MAX_PREFERENCES_BYTES = 32 * 1024


class PreferenceError(RuntimeError):
    """Raised when private summary preferences cannot be used safely."""


def read_preferences(settings: Settings) -> str:
    path = settings.preferences_file
    if not path.is_file():
        return ""
    try:
        if path.stat().st_size > MAX_PREFERENCES_BYTES:
            raise PreferenceError("总结偏好文件超过 32KB，拒绝读取。")
        return path.read_text(encoding="utf-8").strip()
    except UnicodeDecodeError as exc:
        raise PreferenceError("总结偏好文件不是 UTF-8 文本。") from exc
    except OSError as exc:
        raise PreferenceError(f"无法读取总结偏好文件：{path}") from exc


def write_preferences(settings: Settings, text: str) -> Path:
    value = (text or "").strip()
    if not value:
        raise PreferenceError("总结偏好不能为空；如需恢复默认，请使用 clear-summary-preferences。")
    encoded = value.encode("utf-8")
    if len(encoded) > MAX_PREFERENCES_BYTES:
        raise PreferenceError("总结偏好超过 32KB。")

    path = settings.preferences_file
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temp_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)
    return path


def clear_preferences(settings: Settings) -> bool:
    path = settings.preferences_file
    if not path.exists():
        return False
    if not path.is_file():
        raise PreferenceError("总结偏好路径不是普通文件，拒绝删除。")
    path.unlink()
    return True


def effective_instruction(settings: Settings, instruction: str) -> tuple[str, int]:
    preferences = read_preferences(settings)
    parts: list[str] = []
    if preferences:
        parts.append(f"长期总结偏好：\n{preferences}")
    if instruction.strip():
        parts.append(f"本次视频要求：\n{instruction.strip()}")
    return "\n\n".join(parts), len(preferences)
