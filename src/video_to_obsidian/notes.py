"""Safe, human-readable Obsidian note paths."""

from __future__ import annotations

import os
import re
import tempfile
import unicodedata
from pathlib import Path


class NoteWriteError(RuntimeError):
    """Raised when a note cannot be written without violating safety rules."""


_INVALID_FILENAME = re.compile(r"[<>:\"/\\|?*\x00-\x1f]")
_WHITESPACE = re.compile(r"\s+")


def safe_title(title: str, *, max_length: int = 100) -> str:
    value = unicodedata.normalize("NFKC", title or "")
    value = _INVALID_FILENAME.sub(" ", value)
    value = _WHITESPACE.sub(" ", value).strip(" .")
    if not value:
        value = "未命名视频"
    return value[:max_length].rstrip(" .") or "未命名视频"


def safe_identity(identity: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", identity or "").strip("._-")
    if not value:
        raise NoteWriteError("视频稳定身份不能为空。")
    return value[:120]


def note_filename(title: str, identity: str) -> str:
    return f"{safe_title(title)} {safe_identity(identity)}.md"


def write_note(
    vault_path: Path,
    *,
    platform: str,
    title: str,
    identity: str,
    content: str,
) -> Path:
    folder_name = {"douyin": "Douyin", "bilibili": "Bilibili"}.get(platform)
    if folder_name is None:
        raise NoteWriteError(f"不支持的平台：{platform}")
    if not content.strip():
        raise NoteWriteError("拒绝写入空笔记。")

    vault = vault_path.expanduser().resolve()
    if not vault.is_dir():
        raise NoteWriteError(f"Vault 不存在：{vault}")
    folder = (vault / folder_name).resolve()
    try:
        folder.relative_to(vault)
    except ValueError as exc:
        raise NoteWriteError("笔记目录越过 Vault 边界。") from exc
    folder.mkdir(exist_ok=True)
    target = folder / note_filename(title, identity)
    if target.exists():
        raise NoteWriteError(f"同名笔记已存在，拒绝覆盖：{target.name}")

    fd, temporary = tempfile.mkstemp(prefix=".note-", suffix=".tmp", dir=folder)
    temp_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            if not content.endswith("\n"):
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temp_path, target)
        except FileExistsError as exc:
            raise NoteWriteError(f"同名笔记已存在，拒绝覆盖：{target.name}") from exc
    finally:
        temp_path.unlink(missing_ok=True)
    return target

