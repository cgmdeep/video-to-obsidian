import json
from pathlib import Path

import pytest

from video_to_obsidian.zcode import (
    SERVER_NAME,
    ZCodeConfigError,
    build_removed_config,
    build_updated_config,
    update_file,
)


def test_adds_one_stdio_server_without_touching_others() -> None:
    original = {
        "theme": "dark",
        "mcp": {"servers": {"other": {"type": "http", "url": "http://127.0.0.1"}}},
    }
    updated = build_updated_config(original, command="/private/venv/python")
    assert updated["theme"] == "dark"
    assert updated["mcp"]["servers"]["other"] == original["mcp"]["servers"]["other"]
    entry = updated["mcp"]["servers"][SERVER_NAME]
    assert entry["type"] == "stdio"
    assert entry["timeoutMs"] == 1_200_000
    assert "env" not in entry
    assert original.get("mcp", {}).get("servers", {}).get(SERVER_NAME) is None


def test_repeated_same_config_is_idempotent() -> None:
    first = build_updated_config({}, command="python")
    second = build_updated_config(first, command="python")
    assert second == first


def test_refuses_different_existing_entry_without_explicit_replace() -> None:
    payload = {"mcp": {"servers": {SERVER_NAME: {"type": "http", "url": "x"}}}}
    with pytest.raises(ZCodeConfigError):
        build_updated_config(payload, command="python")


def test_update_file_creates_recovery_backup(tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    original = {"mcp": {"servers": {"other": {"type": "http"}}}}
    config.write_text(json.dumps(original), encoding="utf-8")
    backup = update_file(config, command="python")
    assert json.loads(backup.read_text(encoding="utf-8")) == original
    updated = json.loads(config.read_text(encoding="utf-8"))
    assert SERVER_NAME in updated["mcp"]["servers"]


def test_remove_only_our_entry() -> None:
    payload = {
        "mcp": {
            "servers": {
                SERVER_NAME: {"type": "stdio"},
                "other": {"type": "http"},
            }
        }
    }
    updated = build_removed_config(payload)
    assert SERVER_NAME not in updated["mcp"]["servers"]
    assert "other" in updated["mcp"]["servers"]

