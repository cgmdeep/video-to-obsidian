import os
import subprocess
from pathlib import Path

import pytest

from video_to_obsidian import permissions


@pytest.mark.skipif(os.name != "nt", reason="Windows ACL integration check")
def test_windows_acl_integration_diagnostic(tmp_path: Path) -> None:
    path = tmp_path / "acl-diagnostic"
    path.mkdir()
    sid = permissions._windows_current_user_sid()
    assert sid is not None, "whoami did not return the current Windows SID"
    permission = "(OI)(CI)F"
    arguments = [
        str(path),
        "/inheritance:r",
        "/grant:r",
        f"*{sid}:{permission}",
        f"*S-1-5-18:{permission}",
        f"*S-1-5-32-544:{permission}",
    ]
    command = subprocess.run(
        ["icacls.exe", *arguments],
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=30,
    )
    assert command.returncode == 0, {
        "stage": "icacls-grant",
        "returncode": command.returncode,
        "stderr": command.stderr.strip()[:500],
    }
    state = permissions._windows_acl_state(path)
    assert isinstance(state, dict), {"stage": "state-shape", "state": state}
    assert not state.get("unexpected_allow_sids"), {
        "stage": "unexpected-after-grant",
        "state": state,
    }


def test_private_file_and_directory_permissions(tmp_path: Path) -> None:
    directory = tmp_path / "private"
    directory.mkdir()
    path = directory / "config.json"
    path.write_text("{}", encoding="utf-8")

    permissions.ensure_private_path(directory)
    permissions.ensure_private_path(path)

    assert permissions.is_private_path(directory) is True
    assert permissions.is_private_path(path) is True
    if not permissions._is_windows():
        assert directory.stat().st_mode & 0o777 == 0o700
        assert path.stat().st_mode & 0o777 == 0o600


def test_missing_private_path_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(permissions.PrivatePermissionError):
        permissions.ensure_private_path(tmp_path / "missing")


def test_windows_private_check_uses_bounded_acl_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "config.json"
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(permissions, "_is_windows", lambda: True)
    monkeypatch.setattr(
        permissions,
        "_windows_acl_state",
        lambda target: {
            "protected": True,
            "current_has_full_control": True,
            "unexpected_allow_sids": [],
        },
    )

    assert permissions.is_private_path(path) is True


def test_windows_sddl_parser_detects_unexpected_allow(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "config.json"
    path.write_text("{}", encoding="utf-8")
    current = "S-1-5-21-1000"
    monkeypatch.setattr(permissions, "_windows_current_user_sid", lambda: current)
    monkeypatch.setattr(
        permissions,
        "_windows_acl_sddl",
        lambda target: (
            "D:PAI(A;;FA;;;BA)(A;;FA;;;SY)"
            f"(A;;FA;;;{current})(A;;FR;;;BU)"
        ),
    )

    assert permissions._windows_acl_state(path) == {
        "protected": True,
        "current_has_full_control": True,
        "unexpected_allow_sids": ["S-1-5-32-545"],
    }


def test_windows_sddl_local_administrator_and_owner_are_private(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "config.json"
    path.write_text("{}", encoding="utf-8")
    current = "S-1-5-21-1000-500"
    monkeypatch.setattr(permissions, "_windows_current_user_sid", lambda: current)
    monkeypatch.setattr(
        permissions,
        "_windows_acl_sddl",
        lambda target: "D:PAI(A;;FA;;;BA)(A;;FA;;;SY)(A;;FA;;;LA)(A;;FA;;;OW)",
    )

    assert permissions._windows_acl_state(path) == {
        "protected": True,
        "current_has_full_control": True,
        "unexpected_allow_sids": [],
    }


def test_windows_permission_failure_stops_secure_write(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "config.json"
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(permissions, "_is_windows", lambda: True)
    monkeypatch.setattr(
        permissions,
        "_windows_set_private",
        lambda target: False,
    )

    with pytest.raises(permissions.PrivatePermissionError):
        permissions.ensure_private_path(path)


def test_windows_private_acl_removes_unexpected_allow_sids(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "config.json"
    path.write_text("{}", encoding="utf-8")
    calls: list[list[str]] = []
    monkeypatch.setattr(
        permissions,
        "_run_icacls",
        lambda arguments: calls.append(arguments) is None,
    )
    monkeypatch.setattr(
        permissions,
        "_windows_acl_state",
        lambda target: {
            "protected": True,
            "current_has_full_control": True,
            "unexpected_allow_sids": ["S-1-5-32-545", "not-a-sid"],
        },
    )
    monkeypatch.setattr(permissions, "is_private_path", lambda target: True)

    assert permissions._windows_apply_private_acl(path, "S-1-5-21-1000") is True
    assert calls[0][1:3] == ["/inheritance:r", "/grant:r"]
    assert calls[1] == [str(path), "/remove:g", "*S-1-5-32-545"]
