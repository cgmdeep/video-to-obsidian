"""Cross-platform private-file permissions for local user data."""

from __future__ import annotations

import base64
import os
import re
import subprocess
from pathlib import Path


class PrivatePermissionError(RuntimeError):
    """Raised when a sensitive local path cannot be made private."""


_WINDOWS_CHECK_PRIVATE = r"""
$ErrorActionPreference = 'Stop'
$target = $env:VTO_PRIVATE_PATH
if (-not (Test-Path -LiteralPath $target)) { exit 2 }
$acl = Get-Acl -LiteralPath $target
$current = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$allowed = @($current, 'S-1-5-18', 'S-1-5-32-544')
$currentHasFullControl = $false
$unexpectedAllow = $false
foreach ($rule in @($acl.Access)) {
    if ($rule.AccessControlType -ne [System.Security.AccessControl.AccessControlType]::Allow) {
        continue
    }
    try {
        $sid = $rule.IdentityReference.Translate(
            [System.Security.Principal.SecurityIdentifier]
        ).Value
    } catch {
        $unexpectedAllow = $true
        continue
    }
    if ($allowed -notcontains $sid) { $unexpectedAllow = $true }
    if ($sid -eq $current) {
        $full = [System.Security.AccessControl.FileSystemRights]::FullControl
        if (($rule.FileSystemRights -band $full) -eq $full) {
            $currentHasFullControl = $true
        }
    }
}
if ($acl.AreAccessRulesProtected -and $currentHasFullControl -and -not $unexpectedAllow) {
    Write-Output 'true'
    exit 0
}
Write-Output 'false'
exit 0
"""


def _powershell(script: str, path: Path) -> subprocess.CompletedProcess[str]:
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    environment = os.environ.copy()
    environment["VTO_PRIVATE_PATH"] = str(path)
    return subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-EncodedCommand",
            encoded,
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        timeout=30,
    )


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


def _windows_set_private(target: Path) -> bool:
    sid = _windows_current_user_sid()
    if not sid:
        return False
    permission = "(OI)(CI)F" if target.is_dir() else "F"
    grants = [
        f"*{sid}:{permission}",
        f"*S-1-5-18:{permission}",
        f"*S-1-5-32-544:{permission}",
    ]
    arguments = [str(target), "/inheritance:r", "/grant:r", *grants]
    if _run_icacls(arguments) and is_private_path(target):
        return True
    # A pre-existing explicit grant can survive /inheritance:r. Reset only this
    # target to its parent ACL, then apply the bounded grants once more.
    return (
        _run_icacls([str(target), "/reset"])
        and _run_icacls(arguments)
        and is_private_path(target)
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
        result = _powershell(_WINDOWS_CHECK_PRIVATE, target)
        return result.returncode == 0 and result.stdout.strip().casefold() == "true"
    try:
        return target.stat().st_mode & 0o077 == 0
    except OSError:
        return False
