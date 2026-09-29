"""Cross-platform private-file permissions for local user data."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path


class PrivatePermissionError(RuntimeError):
    """Raised when a sensitive local path cannot be made private."""


_SDDL_TRUSTEE_TO_SID = {
    "SY": "S-1-5-18",
    "BA": "S-1-5-32-544",
    "BU": "S-1-5-32-545",
    "AU": "S-1-5-11",
    "WD": "S-1-1-0",
    "OW": "S-1-3-4",
}


def _is_windows() -> bool:
    return os.name == "nt"


def _windows_current_user_sid() -> str | None:
    try:
        result = subprocess.run(
            ["whoami.exe", "/user", "/fo", "csv", "/nh"],
            check=False,
            capture_output=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = re.search(rb"S-1-(?:\d+-)+\d+", result.stdout)
    return match.group(0).decode("ascii") if result.returncode == 0 and match else None


def _run_icacls(arguments: list[str]) -> bool:
    try:
        result = subprocess.run(
            ["icacls.exe", *arguments],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _windows_acl_sddl(target: Path) -> str | None:
    descriptor_fd, descriptor_name = tempfile.mkstemp(suffix=".acl")
    os.close(descriptor_fd)
    descriptor = Path(descriptor_name)
    try:
        descriptor.unlink()
        if not _run_icacls([str(target), "/save", str(descriptor), "/c", "/q"]):
            return None
        text = descriptor.read_text(encoding="utf-16-le")
    except OSError:
        return None
    finally:
        descriptor.unlink(missing_ok=True)
    return next((line.strip() for line in text.splitlines() if line.startswith("D:")), None)


def _windows_acl_state(target: Path) -> dict[str, object] | None:
    sddl = _windows_acl_sddl(target)
    current = _windows_current_user_sid()
    if not sddl or not current:
        return None
    protected = bool(re.match(r"^D:[^()]*P", sddl))
    current_has_full_control = False
    unexpected: list[str] = []
    # LA is the built-in local Administrator account and OW is the current
    # object owner. Neither grants access to an unrelated local user. icacls
    # can abbreviate the current SID as LA when running under that account.
    allowed = {
        current,
        "S-1-5-18",
        "S-1-5-32-544",
        "LA",
        "S-1-3-4",
    }
    for match in re.finditer(r"\(([^()]*)\)", sddl):
        fields = match.group(1).split(";")
        if len(fields) != 6 or fields[0] != "A":
            continue
        rights, trustee = fields[2], fields[5]
        trustee_sid = _SDDL_TRUSTEE_TO_SID.get(trustee, trustee)
        current_trustee = trustee_sid == current or (
            trustee == "LA" and current.endswith("-500")
        )
        if current_trustee and "FA" in rights:
            current_has_full_control = True
        if trustee_sid not in allowed and trustee_sid not in unexpected:
            unexpected.append(trustee_sid)
    return {
        "protected": protected,
        "current_has_full_control": current_has_full_control,
        "unexpected_allow_sids": unexpected,
    }


def _windows_apply_private_acl(target: Path, sid: str) -> bool:
    permission = "(OI)(CI)F" if target.is_dir() else "F"
    grants = [
        f"*{sid}:{permission}",
        f"*S-1-5-18:{permission}",
        f"*S-1-5-32-544:{permission}",
    ]
    if not _run_icacls([str(target), "/inheritance:r", "/grant:r", *grants]):
        return False

    state = _windows_acl_state(target)
    if state is None:
        return False
    unexpected = state.get("unexpected_allow_sids", [])
    if isinstance(unexpected, str):
        unexpected = [unexpected]
    if not isinstance(unexpected, list):
        return False
    removable = [
        f"*{value}"
        for value in unexpected
        if isinstance(value, str) and re.fullmatch(r"S-1-(?:\d+-)+\d+", value)
    ]
    if removable and not _run_icacls([str(target), "/remove:g", *removable]):
        return False
    return is_private_path(target)


def _windows_set_private(target: Path) -> bool:
    sid = _windows_current_user_sid()
    if not sid:
        return False
    if _windows_apply_private_acl(target, sid):
        return True
    # A pre-existing explicit grant can survive /inheritance:r. Reset only this
    # target to its parent ACL, then apply the bounded grants once more.
    return (
        _run_icacls([str(target), "/reset"])
        and _windows_apply_private_acl(target, sid)
    )


def ensure_private_path(path: Path) -> None:
    """Restrict an existing file or directory to the user and OS administrators."""
    target = path.expanduser()
    if not target.exists():
        raise PrivatePermissionError("需要保护的本地路径不存在。")
    if _is_windows():
        if not _windows_set_private(target):
            raise PrivatePermissionError("无法限制本地配置权限；已停止以避免泄露凭据。")
        return
    try:
        os.chmod(target, 0o700 if target.is_dir() else 0o600)
    except OSError as exc:
        raise PrivatePermissionError("无法限制本地配置权限。") from exc


def is_private_path(path: Path) -> bool:
    """Return whether a path excludes access by unrelated local users."""
    target = path.expanduser()
    if not target.exists():
        return False
    if _is_windows():
        state = _windows_acl_state(target)
        return bool(
            state
            and state.get("protected") is True
            and state.get("current_has_full_control") is True
            and not state.get("unexpected_allow_sids")
        )
    try:
        return target.stat().st_mode & 0o077 == 0
    except OSError:
        return False
