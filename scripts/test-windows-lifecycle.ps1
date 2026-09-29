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
$ProfilesIni = Join-Path $env:APPDATA 'Mozilla\Firefox\profiles.ini'
$VaultSentinel = Join-Path $Vault 'lifecycle-vault-sentinel.txt'
$WorkspaceSentinel = Join-Path $Workspace 'lifecycle-workspace-sentinel.txt'

if (-not (Test-Path $Runtime) -or -not (Test-Path $WorkspaceConfig)) {
    throw 'Lifecycle acceptance requires a completed preparation first.'
}

$WorkspacePayload = Get-Content $WorkspaceConfig -Raw | ConvertFrom-Json
$WorkspacePayload.mcp.servers | Add-Member -NotePropertyName 'unrelated-test-server' -NotePropertyValue ([pscustomobject]@{
    type = 'http'
    url = 'http://127.0.0.1:9/mcp'
}) -Force
$WorkspacePayload | ConvertTo-Json -Depth 20 | Set-Content $WorkspaceConfig -Encoding utf8
Set-Content $VaultSentinel 'preserve vault' -Encoding utf8
Set-Content $WorkspaceSentinel 'preserve workspace' -Encoding utf8

$RepairReport = Join-Path $ArtifactsDirectory 'clean-repair.json'
$Repair = Start-Process -FilePath $Setup -ArgumentList @('--prepare-machine', $RepairReport) -Wait -PassThru
if ($Repair.ExitCode -ne 0 -or -not (Test-Path $RepairReport)) {
    throw "Repair of the installed environment failed (exit $($Repair.ExitCode))."
}
$RepairPayload = Get-Content $RepairReport -Raw | ConvertFrom-Json
if (-not $RepairPayload.ok -or $RepairPayload.operation -ne 'repair' -or -not (Test-Path $Runtime)) {
    throw 'Repair did not report success with the stable repair operation.'
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

Write-Host 'Windows install, repair, default uninstall, and private uninstall acceptance passed.'
