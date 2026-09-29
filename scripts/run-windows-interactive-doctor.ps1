[CmdletBinding()]
param(
    [string]$TaskName = 'VideoToObsidian Interactive Doctor',
    [ValidateRange(10, 300)]
    [int]$TimeoutSeconds = 120
)

$ErrorActionPreference = 'Stop'

if (-not $IsWindows -and $PSVersionTable.PSEdition -eq 'Core') {
    throw 'This script only supports Windows.'
}

$zcodeProcess = Get-CimInstance Win32_Process -Filter "Name='ZCode.exe'" |
    Select-Object -First 1
$loggedOnUser = $null
if ($null -ne $zcodeProcess) {
    $owner = Invoke-CimMethod -InputObject $zcodeProcess -MethodName GetOwner
    if ($owner.ReturnValue -eq 0) {
        $loggedOnUser = $owner.User
    }
}
if ([string]::IsNullOrWhiteSpace($loggedOnUser)) {
    $loggedOnIdentity = (Get-CimInstance Win32_ComputerSystem).UserName
    if (-not [string]::IsNullOrWhiteSpace($loggedOnIdentity)) {
        $loggedOnUser = $loggedOnIdentity.Split('\\')[-1]
    }
}
if ([string]::IsNullOrWhiteSpace($loggedOnUser)) {
    throw 'interactive_user_unavailable'
}

$dataRoot = Join-Path $env:LOCALAPPDATA 'VideoToObsidian'
$opsRoot = Join-Path $dataRoot 'ops'
$cli = Join-Path $dataRoot 'runtime\Scripts\video-to-obsidian.exe'
$worker = Join-Path $opsRoot 'interactive-doctor-worker.ps1'
$report = Join-Path $dataRoot 'interactive-doctor-report.json'

if (-not (Test-Path -LiteralPath $cli -PathType Leaf)) {
    throw 'managed_cli_not_found'
}

New-Item -ItemType Directory -Force $opsRoot | Out-Null
Remove-Item -LiteralPath $report -Force -ErrorAction SilentlyContinue

$workerBody = @'
$ErrorActionPreference = 'Stop'
$dataRoot = Join-Path $env:LOCALAPPDATA 'VideoToObsidian'
$cli = Join-Path $dataRoot 'runtime\Scripts\video-to-obsidian.exe'
$report = Join-Path $dataRoot 'interactive-doctor-report.json'
try {
    $raw = & $cli doctor --json 2>&1 | Out-String
    Set-Content -LiteralPath $report -Value $raw -Encoding UTF8
}
catch {
    [pscustomobject]@{
        ok = $false
        error_code = 'interactive_doctor_failed'
        paid_call_performed = $false
    } | ConvertTo-Json -Compress | Set-Content -LiteralPath $report -Encoding UTF8
}
'@
Set-Content -LiteralPath $worker -Value $workerBody -Encoding Unicode

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    throw 'interactive_doctor_task_already_exists'
}

$actionArguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}"' -f $worker
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $actionArguments
$principal = New-ScheduledTaskPrincipal -UserId $loggedOnUser -LogonType Interactive -RunLevel Limited

try {
    Register-ScheduledTask -TaskName $TaskName -Action $action -Principal $principal | Out-Null
    Start-ScheduledTask -TaskName $TaskName

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline -and -not (Test-Path -LiteralPath $report)) {
        Start-Sleep -Milliseconds 500
    }
    if (-not (Test-Path -LiteralPath $report)) {
        $taskInfo = Get-ScheduledTaskInfo -TaskName $TaskName
        [pscustomobject]@{
            ok = $false
            error_code = 'interactive_doctor_timeout'
            last_task_result = $taskInfo.LastTaskResult
            contains_secrets = $false
            contains_local_paths = $false
            paid_call_performed = $false
        } | ConvertTo-Json -Compress
        exit 1
    }

    $payload = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
    [pscustomobject]@{
        ok = [bool]$payload.ok
        required_failed = @(
            $payload.checks |
                Where-Object { $_.required -and -not $_.ok } |
                Select-Object -ExpandProperty name
        )
        check_count = @($payload.checks).Count
        contains_secrets = $false
        contains_local_paths = $false
        paid_call_performed = [bool]$payload.paid_call_performed
    } | ConvertTo-Json -Compress
}
finally {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $worker -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $report -Force -ErrorAction SilentlyContinue
}
