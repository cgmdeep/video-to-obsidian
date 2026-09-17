"""Safe, incremental ZCode MCP configuration."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any


SERVER_NAME = "video-to-obsidian"
DEFAULT_TIMEOUT_MS = 1_200_000


class ZCodeConfigError(RuntimeError):
    pass


def build_updated_config(
    payload: dict[str, Any],
    *,
    command: str,
    args: list[str] | None = None,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    replace_existing: bool = False,
) -> dict[str, Any]:
    if not command.strip():
        raise ZCodeConfigError("MCP command 不能为空。")
    if timeout_ms < 60_000:
        raise ZCodeConfigError("timeoutMs 不能低于 60000。")
    updated = deepcopy(payload)
    mcp = updated.setdefault("mcp", {})
    if not isinstance(mcp, dict):
        raise ZCodeConfigError("ZCode 配置中的 mcp 必须是对象。")
    servers = mcp.setdefault("servers", {})
    if not isinstance(servers, dict):
        raise ZCodeConfigError("ZCode 配置中的 mcp.servers 必须是对象。")
    entry = {
        "type": "stdio",
        "command": command,
        "args": list(args or ["-m", "video_to_obsidian", "mcp"]),
        "enabled": True,
        "timeoutMs": timeout_ms,
    }
    existing = servers.get(SERVER_NAME)
    if existing is not None and existing != entry and not replace_existing:
        raise ZCodeConfigError(
            f"ZCode 已有不同的 {SERVER_NAME} 配置；请人工核对后使用 --replace-existing。"
        )
    servers[SERVER_NAME] = entry
    return updated


def build_removed_config(payload: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(payload)
    mcp = updated.get("mcp")
    if isinstance(mcp, dict):
        servers = mcp.get("servers")
        if isinstance(servers, dict):
            servers.pop(SERVER_NAME, None)
    return updated


def _read(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ZCodeConfigError(f"无法读取 ZCode 配置：{path}") from exc
    if not isinstance(payload, dict):
        raise ZCodeConfigError("ZCode 配置顶层必须是对象。")
    return payload


def _write_with_backup(path: Path, payload: dict[str, Any]) -> Path:
    if not path.is_file():
        raise ZCodeConfigError(f"ZCode 配置不存在：{path}")
    backup = path.with_suffix(path.suffix + ".before-video-to-obsidian.bak")
    if not backup.exists():
        shutil.copy2(path, backup)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, path.stat().st_mode)
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)
    return backup


def update_file(
    path: Path,
    *,
    command: str,
    args: list[str] | None = None,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    replace_existing: bool = False,
) -> Path:
    updated = build_updated_config(
        _read(path),
        command=command,
        args=args,
        timeout_ms=timeout_ms,
        replace_existing=replace_existing,
    )
    return _write_with_backup(path, updated)


def remove_from_file(path: Path) -> Path:
    return _write_with_backup(path, build_removed_config(_read(path)))

