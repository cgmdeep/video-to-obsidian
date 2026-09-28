[CmdletBinding(SupportsShouldProcess)]
param(
    [switch]$Restore,
    [string]$BaselinePath = "$env:LOCALAPPDATA\VideoToObsidian\ops\power-baseline.json"
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Get-AcTimeoutSeconds {
    param(
        [Parameter(Mandatory)][string]$SubGroup,
        [Parameter(Mandatory)][string]$Setting
    )

    $output = (& powercfg.exe /query SCHEME_CURRENT $SubGroup $Setting | Out-String)
    $values = @([regex]::Matches($output, '0x[0-9a-fA-F]{8}') | ForEach-Object {
        [Convert]::ToInt64($_.Value.Substring(2), 16)
    })
    if ($values.Count -lt 2) {
        throw "Unable to read the AC timeout for $Setting."
    }
    return [int64]$values[-2]
}

if ($Restore) {
    if (-not (Test-Path -LiteralPath $BaselinePath)) {
        throw "Power baseline is missing: $BaselinePath"
    }
    $baseline = Get-Content -Raw -LiteralPath $BaselinePath | ConvertFrom-Json
    $standbyMinutes = [math]::Floor([int64]$baseline.standby_timeout_ac_seconds / 60)
    $hibernateMinutes = [math]::Floor([int64]$baseline.hibernate_timeout_ac_seconds / 60)
    if ($PSCmdlet.ShouldProcess('AC power plan', 'restore sleep and hibernate timeouts')) {
        & powercfg.exe /change standby-timeout-ac $standbyMinutes
        if ($LASTEXITCODE -ne 0) { throw 'Failed to restore the AC standby timeout.' }
        & powercfg.exe /change hibernate-timeout-ac $hibernateMinutes
        if ($LASTEXITCODE -ne 0) { throw 'Failed to restore the AC hibernate timeout.' }
    }
    [pscustomobject]@{
        ok = $true
        restored = $true
        standby_timeout_ac_seconds = [int64]$baseline.standby_timeout_ac_seconds
        hibernate_timeout_ac_seconds = [int64]$baseline.hibernate_timeout_ac_seconds
        battery_settings_changed = $false
    } | ConvertTo-Json
    exit 0
}

$baselineDirectory = Split-Path -Parent $BaselinePath
New-Item -ItemType Directory -Path $baselineDirectory -Force | Out-Null
if (-not (Test-Path -LiteralPath $BaselinePath)) {
    $baseline = [ordered]@{
        schema = 'video-to-obsidian/power-baseline/v1'
        recorded_at = (Get-Date).ToUniversalTime().ToString('o')
        standby_timeout_ac_seconds = Get-AcTimeoutSeconds -SubGroup 'SUB_SLEEP' -Setting 'STANDBYIDLE'
        hibernate_timeout_ac_seconds = Get-AcTimeoutSeconds -SubGroup 'SUB_SLEEP' -Setting 'HIBERNATEIDLE'
        battery_settings_changed = $false
    }
    $baseline | ConvertTo-Json | Set-Content -LiteralPath $BaselinePath -Encoding ascii
}

if ($PSCmdlet.ShouldProcess('AC power plan', 'disable sleep and hibernate timeouts')) {
    & powercfg.exe /change standby-timeout-ac 0
    if ($LASTEXITCODE -ne 0) { throw 'Failed to disable the AC standby timeout.' }
    & powercfg.exe /change hibernate-timeout-ac 0
    if ($LASTEXITCODE -ne 0) { throw 'Failed to disable the AC hibernate timeout.' }
}

[pscustomobject]@{
    ok = $true
    restored = $false
    standby_timeout_ac_seconds = 0
    hibernate_timeout_ac_seconds = 0
    battery_settings_changed = $false
    baseline_path = $BaselinePath
} | ConvertTo-Json
