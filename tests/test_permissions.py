from pathlib import Path
from subprocess import CompletedProcess

import pytest

from video_to_obsidian import permissions


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


def test_windows_private_check_uses_bounded_boolean_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "config.json"
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(permissions, "_is_windows", lambda: True)
    monkeypatch.setattr(
        permissions,
        "_powershell",
        lambda script, target: CompletedProcess([], 0, stdout="true\r\n", stderr=""),
    )

    assert permissions.is_private_path(path) is True


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
