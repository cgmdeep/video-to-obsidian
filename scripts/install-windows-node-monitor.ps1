[CmdletBinding(SupportsShouldProcess)]
param(
    [switch]$Remove,
    [switch]$NoZCodeRecovery
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$taskName = 'VideoToObsidian Node Monitor'
$opsDirectory = Join-Path $env:LOCALAPPDATA 'VideoToObsidian\ops'
$sourceScript = Join-Path $PSScriptRoot 'windows-node-monitor.ps1'
$monitorScript = Join-Path $opsDirectory 'windows-node-monitor.ps1'
$sourcePowerScript = Join-Path $PSScriptRoot 'set-windows-node-power.ps1'
$powerScript = Join-Path $opsDirectory 'set-windows-node-power.ps1'
$statusPath = Join-Path $env:LOCALAPPDATA 'VideoToObsidian\state\node-status.json'

if ($Remove) {
    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
        if ($PSCmdlet.ShouldProcess($taskName, 'remove the node monitor task')) {
            Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        }
    }
    if (Test-Path -LiteralPath $monitorScript) {
        if ($PSCmdlet.ShouldProcess($monitorScript, 'remove the node monitor script')) {
            Remove-Item -LiteralPath $monitorScript -Force
        }
    }
    [pscustomobject]@{
        ok = $true
        removed = $true
        task_name = $taskName
        private_data_preserved = $true
    } | ConvertTo-Json
    exit 0
}

if (-not (Test-Path -LiteralPath $sourceScript)) {
    throw "Node monitor script is missing: $sourceScript"
}

New-Item -ItemType Directory -Path $opsDirectory -Force | Out-Null
Copy-Item -LiteralPath $sourceScript -Destination $monitorScript -Force
if (Test-Path -LiteralPath $sourcePowerScript) {
    Copy-Item -LiteralPath $sourcePowerScript -Destination $powerScript -Force
}

$arguments = @(
    '-NoProfile',
    '-NonInteractive',
    '-ExecutionPolicy', 'Bypass',
    '-WindowStyle', 'Hidden',
    '-File', ('"{0}"' -f $monitorScript)
)
if (-not $NoZCodeRecovery) {
    $arguments += '-StartZCodeIfMissing'
}

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ($arguments -join ' ')
$logonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$repeatTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 2)
$principal = New-ScheduledTaskPrincipal `
    -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive `
    -RunLevel Limited

if ($PSCmdlet.ShouldProcess($taskName, 'install the node monitor task')) {
    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Trigger @($logonTrigger, $repeatTrigger) `
        -Settings $settings `
        -Principal $principal `
        -Description 'Keeps ZCode available after logon and writes a secret-free health snapshot every five minutes.' `
        -Force | Out-Null
}

$monitorArguments = @('-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', $monitorScript)
if (-not $NoZCodeRecovery) {
    $monitorArguments += '-StartZCodeIfMissing'
}
& powershell.exe @monitorArguments | Out-Null

$task = Get-ScheduledTask -TaskName $taskName
[pscustomobject]@{
    ok = $true
    removed = $false
    task_name = $taskName
    task_state = [string]$task.State
    interval_minutes = 5
    zcode_recovery = -not $NoZCodeRecovery
    status_path = $statusPath
    paid_call_performed = $false
} | ConvertTo-Json
