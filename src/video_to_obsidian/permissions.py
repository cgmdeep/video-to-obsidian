"""Cross-platform private-file permissions for local user data."""

from __future__ import annotations

import base64
import os
import subprocess
from pathlib import Path


class PrivatePermissionError(RuntimeError):
    """Raised when a sensitive local path cannot be made private."""


_WINDOWS_SET_PRIVATE = r"""
$ErrorActionPreference = 'Stop'
$target = $env:VTO_PRIVATE_PATH
if (-not (Test-Path -LiteralPath $target)) { throw 'private path does not exist' }
$item = Get-Item -LiteralPath $target -Force
$acl = Get-Acl -LiteralPath $target
$acl.SetAccessRuleProtection($true, $false)
foreach ($rule in @($acl.Access)) {
    [void]$acl.RemoveAccessRuleSpecific($rule)
}
$inheritance = [System.Security.AccessControl.InheritanceFlags]::None
if ($item.PSIsContainer) {
    $inheritance = [System.Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit'
}
$propagation = [System.Security.AccessControl.PropagationFlags]::None
$allow = [System.Security.AccessControl.AccessControlType]::Allow
$full = [System.Security.AccessControl.FileSystemRights]::FullControl
$sids = @(
    [System.Security.Principal.WindowsIdentity]::GetCurrent().User,
    [System.Security.Principal.SecurityIdentifier]::new('S-1-5-18'),
    [System.Security.Principal.SecurityIdentifier]::new('S-1-5-32-544')
)
foreach ($sid in $sids) {
    $entry = [System.Security.AccessControl.FileSystemAccessRule]::new(
        $sid, $full, $inheritance, $propagation, $allow
    )
    [void]$acl.AddAccessRule($entry)
}
Set-Acl -LiteralPath $target -AclObject $acl
"""


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


def ensure_private_path(path: Path) -> None:
    """Restrict an existing file or directory to the user and OS administrators."""
    target = path.expanduser()
    if not target.exists():
        raise PrivatePermissionError("需要保护的本地路径不存在。")
    if _is_windows():
        result = _powershell(_WINDOWS_SET_PRIVATE, target)
        if result.returncode != 0:
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
