[CmdletBinding()]
param(
    [switch]$StartZCodeIfMissing,
    [string]$OutputPath = "$env:LOCALAPPDATA\VideoToObsidian\state\node-status.json"
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Get-ServiceState {
    param([Parameter(Mandatory)][string]$Name)

    $service = Get-Service -Name $Name -ErrorAction SilentlyContinue
    if ($null -eq $service) {
        return [pscustomobject]@{ installed = $false; running = $false; start_type = $null }
    }

    $cim = Get-CimInstance Win32_Service -Filter "Name='$Name'" -ErrorAction SilentlyContinue
    return [pscustomobject]@{
        installed  = $true
        running    = $service.Status -eq 'Running'
        start_type = if ($null -ne $cim) { $cim.StartMode } else { $null }
    }
}

function Get-DoctorSummary {
    param([Parameter(Mandatory)][string]$PythonPath)

    if (-not (Test-Path -LiteralPath $PythonPath)) {
        return [pscustomobject]@{
            available = $false
            ok = $false
            paid_call_performed = $false
            checks = @()
            error = 'runtime_missing'
        }
    }

    try {
        $raw = (& $PythonPath -m video_to_obsidian doctor --json 2>$null | Out-String).Trim()
        if (-not $raw) {
            throw 'doctor_empty_output'
        }
        $doctor = $raw | ConvertFrom-Json
        $checks = @($doctor.checks | ForEach-Object {
            [pscustomobject]@{
                name = [string]$_.name
                ok = [bool]$_.ok
                required = [bool]$_.required
            }
        })
        return [pscustomobject]@{
            available = $true
            ok = [bool]$doctor.ok
            paid_call_performed = [bool]$doctor.paid_call_performed
            checks = $checks
            error = $null
        }
    }
    catch {
        return [pscustomobject]@{
            available = $true
            ok = $false
            paid_call_performed = $false
            checks = @()
            error = 'doctor_failed'
        }
    }
}

$mutex = [Threading.Mutex]::new($false, 'Local\VideoToObsidian.NodeMonitor')
$lockTaken = $false
try {
    $lockTaken = $mutex.WaitOne(0)
    if (-not $lockTaken) {
        exit 0
    }

    $installRoot = Join-Path $env:LOCALAPPDATA 'VideoToObsidian'
    $pythonPath = Join-Path $installRoot 'runtime\Scripts\python.exe'
    $zcodePath = Join-Path $env:LOCALAPPDATA 'Programs\ZCode\ZCode.exe'

    $zcodeProcesses = @(Get-Process -Name ZCode -ErrorAction SilentlyContinue)
    $zcodeStarted = $false
    if ($StartZCodeIfMissing -and $zcodeProcesses.Count -eq 0 -and (Test-Path -LiteralPath $zcodePath)) {
        Start-Process -FilePath $zcodePath
        Start-Sleep -Seconds 3
        $zcodeProcesses = @(Get-Process -Name ZCode -ErrorAction SilentlyContinue)
        $zcodeStarted = $zcodeProcesses.Count -gt 0
    }

    $os = Get-CimInstance Win32_OperatingSystem
    $system = Get-CimInstance Win32_ComputerSystem
    $drive = Get-PSDrive -Name C
    $doctor = Get-DoctorSummary -PythonPath $pythonPath

    $status = [ordered]@{
        schema = 'video-to-obsidian/node-status/v1'
        generated_at = (Get-Date).ToUniversalTime().ToString('o')
        paid_call_performed = $false
        machine = [ordered]@{
            computer_name = $env:COMPUTERNAME
            memory_total_gb = [math]::Round($system.TotalPhysicalMemory / 1GB, 1)
            memory_free_gb = [math]::Round($os.FreePhysicalMemory * 1KB / 1GB, 1)
            c_drive_free_gb = [math]::Round($drive.Free / 1GB, 1)
        }
        connectivity = [ordered]@{
            tailscale = Get-ServiceState -Name 'Tailscale'
            netbird = Get-ServiceState -Name 'Netbird'
            sshd = Get-ServiceState -Name 'sshd'
        }
        runtime = [ordered]@{
            installed = Test-Path -LiteralPath $pythonPath
            zcode_installed = Test-Path -LiteralPath $zcodePath
            zcode_running = $zcodeProcesses.Count -gt 0
            zcode_started_by_monitor = $zcodeStarted
        }
        doctor = $doctor
    }

    $outputDirectory = Split-Path -Parent $OutputPath
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
    $temporaryPath = "$OutputPath.tmp"
    $status | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $temporaryPath -Encoding utf8
    Move-Item -LiteralPath $temporaryPath -Destination $OutputPath -Force
    $status | ConvertTo-Json -Depth 8
}
finally {
    if ($lockTaken) {
        $mutex.ReleaseMutex()
    }
    $mutex.Dispose()
}
