"""Safe, human-readable Obsidian note paths."""

from __future__ import annotations

import os
import re
import tempfile
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any


class NoteWriteError(RuntimeError):
    """Raised when a note cannot be written without violating safety rules."""


_INVALID_FILENAME = re.compile(r"[<>:\"/\\|?*\x00-\x1f]")
_WHITESPACE = re.compile(r"\s+")
_FRONTMATTER_LIMIT_BYTES = 64 * 1024
_IGNORED_VAULT_DIRECTORIES = {".obsidian", ".trash", ".stversions", "#SyncVersion"}


def _is_active_vault_markdown(vault: Path, path: Path) -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    try:
        relative_parts = path.relative_to(vault).parts
    except ValueError:
        return False
    return not any(
        part.startswith(".") or part in _IGNORED_VAULT_DIRECTORIES
        for part in relative_parts[:-1]
    )


def _managed_identity(frontmatter: str) -> str:
    generated = re.search(
        r'(?m)^generated_by:\s*["\']?video-to-obsidian["\']?\s*$',
        frontmatter,
    )
    if generated is None:
        return ""
    for field in ("source_uid", "identity"):
        match = re.search(
            rf'(?m)^{field}:\s*["\']?([^"\'\r\n]+)["\']?\s*$',
            frontmatter,
        )
        if match:
            return match.group(1).strip()
    return ""


def audit_vault(vault_path: Path) -> dict[str, Any]:
    """Read-only audit of managed source identities in an Obsidian Vault."""

    vault = vault_path.expanduser().resolve()
    if not vault.is_dir():
        raise NoteWriteError(f"Vault 不存在：{vault}")

    markdown_files = 0
    managed: dict[str, list[str]] = defaultdict(list)
    unreadable_files = 0
    for path in vault.rglob("*.md"):
        if not _is_active_vault_markdown(vault, path):
            continue
        markdown_files += 1
        try:
            with path.open("r", encoding="utf-8") as handle:
                prefix = handle.read(_FRONTMATTER_LIMIT_BYTES)
        except (OSError, UnicodeError):
            unreadable_files += 1
            continue
        if not prefix.startswith("---\n"):
            continue
        frontmatter_end = prefix.find("\n---", 4)
        if frontmatter_end == -1:
            continue
        identity = _managed_identity(prefix[:frontmatter_end])
        if identity:
            managed[identity].append(path.relative_to(vault).as_posix())

    duplicate_groups = [
        {
            "identity": identity,
            "count": len(paths),
            "paths": sorted(paths),
        }
        for identity, paths in sorted(managed.items())
        if len(paths) > 1
    ]
    return {
        "ok": not duplicate_groups and unreadable_files == 0,
        "paid_call_performed": False,
        "vault": str(vault),
        "markdown_files": markdown_files,
        "managed_notes": sum(len(paths) for paths in managed.values()),
        "managed_identities": len(managed),
        "duplicate_groups": duplicate_groups,
        "unreadable_files": unreadable_files,
    }


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


def find_note_by_identity(vault_path: Path, platform: str, identity: str) -> Path | None:
    folder_name = {"douyin": "Douyin", "bilibili": "Bilibili"}.get(platform)
    if folder_name is None:
        raise NoteWriteError(f"不支持的平台：{platform}")
    vault = vault_path.expanduser().resolve()
    if not vault.is_dir():
        return None

    safe_id = safe_identity(identity)
    suffix = f" {safe_id}.md"
    bilibili_match = re.fullmatch(r"bilibili_(BV[A-Za-z0-9]+)_p(\d+)", identity)
    source_uid = (
        f"bilibili:{bilibili_match.group(1)}:p{int(bilibili_match.group(2)):02d}"
        if bilibili_match
        else f"douyin:{identity}"
    )
    identity_markers = {
        f'identity: "{identity}"',
        f"identity: {identity}",
        f'source_uid: "{source_uid}"',
        f"source_uid: {source_uid}",
    }

    matches: list[Path] = []
    for path in vault.rglob("*.md"):
        if not _is_active_vault_markdown(vault, path):
            continue
        if path.name.endswith(suffix):
            matches.append(path)
            continue
        try:
            with path.open("r", encoding="utf-8") as handle:
                prefix = handle.read(_FRONTMATTER_LIMIT_BYTES)
        except (OSError, UnicodeError):
            continue
        if not prefix.startswith("---\n"):
            continue
        frontmatter_end = prefix.find("\n---", 4)
        if frontmatter_end == -1:
            continue
        frontmatter = prefix[:frontmatter_end]
        if not _managed_identity(frontmatter):
            continue
        if any(marker in frontmatter for marker in identity_markers):
            matches.append(path)

    matches = sorted(set(matches))
    if len(matches) > 1:
        raise NoteWriteError(f"发现多个相同稳定身份的笔记：{identity}")
    return matches[0] if matches else None


def write_candidate(
    candidates_dir: Path,
    *,
    title: str,
    identity: str,
    content: str,
    marker: str,
) -> Path:
    if not content.strip():
        raise NoteWriteError("拒绝写入空候选笔记。")
    folder = candidates_dir.expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{safe_title(title)} {safe_identity(identity)}.{safe_identity(marker)}.md"
    target = folder / name
    if target.exists():
        raise NoteWriteError(f"同名候选已存在，拒绝覆盖：{target.name}")
    fd, temporary = tempfile.mkstemp(prefix=".candidate-", suffix=".tmp", dir=folder)
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
            raise NoteWriteError(f"同名候选已存在，拒绝覆盖：{target.name}") from exc
    finally:
        temp_path.unlink(missing_ok=True)
    return target
