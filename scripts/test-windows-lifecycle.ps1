[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Setup,
    [Parameter(Mandatory = $true)]
    [string]$ArtifactsDirectory
)

$ErrorActionPreference = 'Stop'
$Setup = (Resolve-Path $Setup).Path
$ArtifactsDirectory = [IO.Path]::GetFullPath($ArtifactsDirectory)
New-Item -ItemType Directory -Force $ArtifactsDirectory | Out-Null

$Vault = Join-Path ([Environment]::GetFolderPath('MyDocuments')) '视知库'
$Workspace = Join-Path ([Environment]::GetFolderPath('MyDocuments')) '视知库助手'
$WorkspaceConfig = Join-Path $Workspace '.zcode\config.json'
$Runtime = Join-Path $env:LOCALAPPDATA 'VideoToObsidian\runtime\Scripts\video-to-obsidian.exe'
$PayloadRoot = Join-Path $env:LOCALAPPDATA 'VideoToObsidian\payload'
$RoamingRoot = Join-Path $env:APPDATA 'VideoToObsidian'
$LocalRoot = Join-Path $env:LOCALAPPDATA 'VideoToObsidian'
$ConfigPath = Join-Path $RoamingRoot 'config.toml'
$ProfilesIni = Join-Path $env:APPDATA 'Mozilla\Firefox\profiles.ini'
$VaultSentinel = Join-Path $Vault 'lifecycle-vault-sentinel.txt'
$WorkspaceSentinel = Join-Path $Workspace 'lifecycle-workspace-sentinel.txt'
$SourceUninstall = Join-Path $PSScriptRoot 'uninstall.ps1'

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

public static class VtoCredentialProbe
{
    [DllImport("advapi32.dll", EntryPoint = "CredReadW", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool CredRead(string target, int type, int flags, out IntPtr credential);

    [DllImport("advapi32.dll")]
    private static extern void CredFree(IntPtr buffer);

    public static bool Exists(string target)
    {
        IntPtr credential;
        var found = CredRead(target, 1, 0, out credential);
        if (found && credential != IntPtr.Zero)
        {
            CredFree(credential);
        }
        return found;
    }
}
'@

function Test-KimiCredentialExists {
    return [VtoCredentialProbe]::Exists('video-to-obsidian') -or
        [VtoCredentialProbe]::Exists('KIMI_API_KEY@video-to-obsidian')
}

if (-not (Test-Path $Runtime) -or -not (Test-Path $WorkspaceConfig) -or -not (Test-Path $SourceUninstall)) {
    throw 'Lifecycle acceptance requires a completed preparation first.'
}

# Store a deliberately non-provider test value through the real keyring backend.
# The probe only checks whether the generic credential target exists; it never
# reads or prints the credential blob.
$TestCredentialValue = 'lifecycle-dummy-value-not-a-provider-key'
$SetKeyText = $TestCredentialValue | & $Runtime set-kimi-key --stdin --json
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to create the lifecycle test credential.'
}
$SetKeyPayload = $SetKeyText | ConvertFrom-Json
if (-not $SetKeyPayload.ok -or $SetKeyPayload.secret_displayed -or $SetKeyPayload.paid_call_performed) {
    throw 'Lifecycle test credential creation returned an unsafe result.'
}
if (-not (Test-KimiCredentialExists)) {
    throw 'Lifecycle test credential was not written to Windows Credential Manager.'
}

$WorkspacePayload = Get-Content $WorkspaceConfig -Raw | ConvertFrom-Json
$WorkspacePayload.mcp.servers | Add-Member -NotePropertyName 'unrelated-test-server' -NotePropertyValue ([pscustomobject]@{
    type = 'http'
    url = 'http://127.0.0.1:9/mcp'
}) -Force
$WorkspacePayload | ConvertTo-Json -Depth 20 | Set-Content $WorkspaceConfig -Encoding utf8
Set-Content $VaultSentinel 'preserve vault' -Encoding utf8
Set-Content $WorkspaceSentinel 'preserve workspace' -Encoding utf8

# Exercise the repository's documented PowerShell uninstaller separately from
# the graphical installer's own uninstall command. GitHub's disposable Windows
# runner keeps this destructive check isolated from a real user machine.
& $SourceUninstall -Confirm:$false
if ((Test-Path $Runtime) -or (Test-Path $PayloadRoot)) {
    throw 'Source uninstall left installed core files behind.'
}
if (-not (Test-KimiCredentialExists)) {
    throw 'Source uninstall unexpectedly deleted the preserved Kimi credential.'
}
if (-not (Test-Path $VaultSentinel) -or -not (Test-Path $WorkspaceSentinel) -or -not (Test-Path $ProfilesIni)) {
    throw 'Source uninstall removed user-owned content.'
}
$AfterSourceUninstall = Get-Content $WorkspaceConfig -Raw | ConvertFrom-Json
if ($AfterSourceUninstall.mcp.servers.PSObject.Properties.Name -contains 'video-to-obsidian') {
    throw 'Source uninstall left the managed MCP entry behind.'
}
if ($AfterSourceUninstall.mcp.servers.PSObject.Properties.Name -notcontains 'unrelated-test-server') {
    throw 'Source uninstall modified an unrelated MCP entry.'
}

$SourceReinstallReport = Join-Path $ArtifactsDirectory 'clean-source-reinstall.json'
$SourceReinstall = Start-Process -FilePath $Setup -ArgumentList @('--prepare-machine', $SourceReinstallReport) -Wait -PassThru
if ($SourceReinstall.ExitCode -ne 0 -or -not (Test-Path $SourceReinstallReport)) {
    throw "Reinstall after source uninstall failed (exit $($SourceReinstall.ExitCode))."
}
$SourceReinstallPayload = Get-Content $SourceReinstallReport -Raw | ConvertFrom-Json
if (-not $SourceReinstallPayload.ok -or $SourceReinstallPayload.operation -ne 'install' -or -not (Test-Path $Runtime)) {
    throw 'Reinstall after source uninstall did not restore the installed core.'
}
$AfterSourceReinstall = Get-Content $WorkspaceConfig -Raw | ConvertFrom-Json
$SourceReinstallServerNames = @($AfterSourceReinstall.mcp.servers.PSObject.Properties.Name)
if ($SourceReinstallServerNames -notcontains 'video-to-obsidian' -or $SourceReinstallServerNames -notcontains 'unrelated-test-server') {
    throw 'Reinstall after source uninstall did not restore managed MCP while preserving unrelated configuration.'
}

# A real user may select a custom Vault and transcript profile during the first
# installation. Headless repair must reuse both instead of silently reverting
# to installer defaults.
$CustomVault = Join-Path ([Environment]::GetFolderPath('MyDocuments')) '自定义视知库'
New-Item -ItemType Directory -Force $CustomVault | Out-Null
Set-Content (Join-Path $CustomVault 'custom-vault-sentinel.txt') 'preserve custom vault' -Encoding utf8
$ConfigText = Get-Content $ConfigPath -Raw
$CustomVaultJson = $CustomVault | ConvertTo-Json -Compress
$ConfigText = $ConfigText -replace '(?m)^vault_path = .*$', "vault_path = $CustomVaultJson"
$ConfigText = $ConfigText -replace '(?m)^profile = .*$', 'profile = "transcript"'
Set-Content $ConfigPath $ConfigText -Encoding utf8

$RepairReport = Join-Path $ArtifactsDirectory 'clean-repair.json'
$Repair = Start-Process -FilePath $Setup -ArgumentList @('--prepare-machine', $RepairReport) -Wait -PassThru
if ($Repair.ExitCode -ne 0 -or -not (Test-Path $RepairReport)) {
    throw "Repair of the installed environment failed (exit $($Repair.ExitCode))."
}
$RepairPayload = Get-Content $RepairReport -Raw | ConvertFrom-Json
if (-not $RepairPayload.ok -or $RepairPayload.operation -ne 'repair' -or -not (Test-Path $Runtime)) {
    throw 'Repair did not report success with the stable repair operation.'
}
if (-not (Test-Path (Join-Path $CustomVault 'custom-vault-sentinel.txt'))) {
    throw 'Repair did not preserve the configured custom Vault.'
}
$AfterRepair = Get-Content $WorkspaceConfig -Raw | ConvertFrom-Json
$RepairServerNames = @($AfterRepair.mcp.servers.PSObject.Properties.Name)
if ($RepairServerNames -notcontains 'video-to-obsidian' -or $RepairServerNames -notcontains 'unrelated-test-server') {
    throw 'Repair did not preserve both managed and unrelated MCP entries.'
}

$UninstallReport = Join-Path $ArtifactsDirectory 'clean-uninstall.json'
$Uninstall = Start-Process -FilePath $Setup -ArgumentList @('--uninstall-machine', $UninstallReport) -Wait -PassThru
if ($Uninstall.ExitCode -ne 0 -or -not (Test-Path $UninstallReport)) {
    throw "Default uninstall failed (exit $($Uninstall.ExitCode))."
}
$UninstallPayload = Get-Content $UninstallReport -Raw | ConvertFrom-Json
if (-not $UninstallPayload.ok -or -not $UninstallPayload.core_removed -or -not $UninstallPayload.managed_mcp_removed) {
    throw 'Default uninstall report did not confirm core and managed MCP removal.'
}
if (-not $UninstallPayload.vault_preserved -or -not $UninstallPayload.workspace_preserved -or -not $UninstallPayload.firefox_profile_preserved) {
    throw 'Default uninstall did not preserve the Vault, workspace, and Firefox profile.'
}
if ((Test-Path $Runtime) -or (Test-Path $PayloadRoot)) {
    throw 'Default uninstall left installed core files behind.'
}
if (-not (Test-KimiCredentialExists)) {
    throw 'Default uninstall unexpectedly deleted the preserved Kimi credential.'
}
if (-not (Test-Path $VaultSentinel) -or -not (Test-Path $WorkspaceSentinel) -or -not (Test-Path $ProfilesIni)) {
    throw 'Default uninstall removed user-owned content.'
}
$AfterUninstall = Get-Content $WorkspaceConfig -Raw | ConvertFrom-Json
if ($AfterUninstall.mcp.servers.PSObject.Properties.Name -contains 'video-to-obsidian') {
    throw 'Default uninstall left the managed MCP entry behind.'
}
if ($AfterUninstall.mcp.servers.PSObject.Properties.Name -notcontains 'unrelated-test-server') {
    throw 'Default uninstall modified an unrelated MCP entry.'
}

$ReinstallReport = Join-Path $ArtifactsDirectory 'clean-reinstall.json'
$Reinstall = Start-Process -FilePath $Setup -ArgumentList @('--prepare-machine', $ReinstallReport) -Wait -PassThru
if ($Reinstall.ExitCode -ne 0 -or -not (Test-Path $ReinstallReport)) {
    throw "Reinstall after uninstall failed (exit $($Reinstall.ExitCode))."
}
$ReinstallPayload = Get-Content $ReinstallReport -Raw | ConvertFrom-Json
if (-not $ReinstallPayload.ok -or $ReinstallPayload.operation -ne 'install' -or -not (Test-Path $Runtime)) {
    throw 'Reinstall did not restore the installed core.'
}
$AfterReinstall = Get-Content $WorkspaceConfig -Raw | ConvertFrom-Json
$ServerNames = @($AfterReinstall.mcp.servers.PSObject.Properties.Name)
if ($ServerNames -notcontains 'video-to-obsidian' -or $ServerNames -notcontains 'unrelated-test-server') {
    throw 'Reinstall did not restore the managed MCP while preserving unrelated configuration.'
}

New-Item -ItemType Directory -Force $RoamingRoot | Out-Null
Set-Content (Join-Path $RoamingRoot 'private-sentinel.txt') 'remove private data' -Encoding utf8
Set-Content (Join-Path $LocalRoot 'private-sentinel.txt') 'remove private data' -Encoding utf8
$PrivateReport = Join-Path $ArtifactsDirectory 'clean-private-uninstall.json'
$PrivateUninstall = Start-Process -FilePath $Setup -ArgumentList @(
    '--uninstall-machine',
    $PrivateReport,
    '--remove-private-data'
) -Wait -PassThru
if ($PrivateUninstall.ExitCode -ne 0 -or -not (Test-Path $PrivateReport)) {
    throw "Private uninstall failed (exit $($PrivateUninstall.ExitCode))."
}
$PrivatePayload = Get-Content $PrivateReport -Raw | ConvertFrom-Json
if (-not $PrivatePayload.ok -or -not $PrivatePayload.private_data_removed) {
    throw 'Private uninstall did not confirm private-data removal.'
}
if ((Test-Path $RoamingRoot) -or (Test-Path $LocalRoot)) {
    throw 'Private uninstall left managed private-data roots behind.'
}
if (Test-KimiCredentialExists) {
    throw 'Private uninstall left the Kimi credential in Windows Credential Manager.'
}
if (-not (Test-Path $VaultSentinel) -or -not (Test-Path $WorkspaceSentinel) -or -not (Test-Path $ProfilesIni)) {
    throw 'Private uninstall removed the Vault, workspace, or Firefox profile.'
}
$AfterPrivateUninstall = Get-Content $WorkspaceConfig -Raw | ConvertFrom-Json
if ($AfterPrivateUninstall.mcp.servers.PSObject.Properties.Name -contains 'video-to-obsidian') {
    throw 'Private uninstall left the managed MCP entry behind.'
}
if ($AfterPrivateUninstall.mcp.servers.PSObject.Properties.Name -notcontains 'unrelated-test-server') {
    throw 'Private uninstall modified an unrelated MCP entry.'
}

Write-Host 'Windows install, source uninstall, repair, default uninstall, and private uninstall acceptance passed.'
