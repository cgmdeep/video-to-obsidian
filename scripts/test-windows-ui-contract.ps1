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

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

function Get-InstallerControl {
    param(
        [Parameter(Mandatory = $true)]
        [System.Windows.Automation.AutomationElement]$Root,
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [System.Windows.Automation.ControlType]$ControlType
    )

    $NameCondition = [System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::NameProperty,
        $Name
    )
    $TypeCondition = [System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
        $ControlType
    )
    $Condition = [System.Windows.Automation.AndCondition]::new(
        $NameCondition,
        $TypeCondition
    )
    return $Root.FindFirst(
        [System.Windows.Automation.TreeScope]::Descendants,
        $Condition
    )
}

function Invoke-InstallerButton {
    param(
        [Parameter(Mandatory = $true)]
        [System.Windows.Automation.AutomationElement]$Root,
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $Button = Get-InstallerControl `
        -Root $Root `
        -Name $Name `
        -ControlType ([System.Windows.Automation.ControlType]::Button)
    if (-not $Button) {
        throw "Installer button is unavailable: $Name"
    }
    $Pattern = $null
    if (-not $Button.TryGetCurrentPattern(
        [System.Windows.Automation.InvokePattern]::Pattern,
        [ref]$Pattern
    )) {
        throw "Installer button does not expose InvokePattern: $Name"
    }
    ([System.Windows.Automation.InvokePattern]$Pattern).Invoke()
}

function Wait-InstallerEnabled {
    param(
        [Parameter(Mandatory = $true)]
        [System.Windows.Automation.AutomationElement]$Root,
        [int]$TimeoutSeconds = 30
    )

    $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $Deadline) {
        try {
            if ($Root.Current.IsEnabled) {
                return
            }
        } catch {
            # The window may briefly refresh its automation tree after an async action.
        }
        Start-Sleep -Milliseconds 200
    }
    throw 'Installer did not return to an enabled state.'
}

function Close-InstallerMessageBox {
    param(
        [Parameter(Mandatory = $true)]
        [int]$ProcessId,
        [Parameter(Mandatory = $true)]
        [string]$ExpectedText,
        [int]$TimeoutSeconds = 30
    )

    $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $Deadline) {
        $Windows = [System.Windows.Automation.AutomationElement]::RootElement.FindAll(
            [System.Windows.Automation.TreeScope]::Descendants,
            ([System.Windows.Automation.PropertyCondition]::new(
                [System.Windows.Automation.AutomationElement]::ProcessIdProperty,
                $ProcessId
            ))
        )
        foreach ($Window in $Windows) {
            if (
                $Window.Current.ControlType -ne
                [System.Windows.Automation.ControlType]::Window
            ) {
                continue
            }
            if ($Window.Current.Name -eq '视知库安装与连接向导') {
                continue
            }
            $Text = @(
                $Window.Current.Name
                $Window.FindAll(
                    [System.Windows.Automation.TreeScope]::Descendants,
                    [System.Windows.Automation.Condition]::TrueCondition
                ) | ForEach-Object { $_.Current.Name }
            ) -join "`n"
            if ($Text -notmatch [regex]::Escape($ExpectedText)) {
                continue
            }
            $Dismiss = @('OK', '确定') | ForEach-Object {
                Get-InstallerControl `
                    -Root $Window `
                    -Name $_ `
                    -ControlType ([System.Windows.Automation.ControlType]::Button)
            } | Where-Object { $_ } | Select-Object -First 1
            if (-not $Dismiss) {
                throw "Installer message box has no dismiss button: $ExpectedText"
            }
            $Pattern = $null
            if (-not $Dismiss.TryGetCurrentPattern(
                [System.Windows.Automation.InvokePattern]::Pattern,
                [ref]$Pattern
            )) {
                throw "Installer message-box button does not expose InvokePattern: $ExpectedText"
            }
            ([System.Windows.Automation.InvokePattern]$Pattern).Invoke()
            return
        }
        Start-Sleep -Milliseconds 200
    }
    throw "Installer message box did not appear: $ExpectedText"
}

$RequiredButtons = @(
    '安装 / 修复本机',
    '用 Obsidian 打开',
    '安全保存并自动补齐',
    '登录抖音',
    '登录B站',
    '安装 / 打开 ZCode',
    '官方微信连接教程',
    '用 ZCode 打开视知库助手',
    '打开工作区文件夹',
    '复制工作区路径',
    '重新检查',
    '导出脱敏诊断报告',
    '安全卸载（保留笔记）'
)

$Process = $null
try {
    $Process = Start-Process -FilePath $Setup -PassThru
    $Deadline = (Get-Date).AddSeconds(30)
    while ($Process.MainWindowHandle -eq 0 -and (Get-Date) -lt $Deadline) {
        Start-Sleep -Milliseconds 250
        $Process.Refresh()
    }
    if ($Process.HasExited -or $Process.MainWindowHandle -eq 0) {
        throw 'Installer did not expose an interactive window within 30 seconds.'
    }

    $Root = [System.Windows.Automation.AutomationElement]::FromHandle(
        $Process.MainWindowHandle
    )
    if ($Root.Current.Name -ne '视知库安装与连接向导') {
        throw "Unexpected installer window title: $($Root.Current.Name)"
    }

    $Descendants = $Root.FindAll(
        [System.Windows.Automation.TreeScope]::Descendants,
        [System.Windows.Automation.Condition]::TrueCondition
    )
    $ButtonNames = @(
        foreach ($Control in $Descendants) {
            if (
                $Control.Current.ControlType -eq
                [System.Windows.Automation.ControlType]::Button -and
                $Control.Current.Name
            ) {
                $Control.Current.Name
            }
        }
    ) | Sort-Object -Unique
    $Missing = @($RequiredButtons | Where-Object { $ButtonNames -notcontains $_ })
    if ($Missing.Count -gt 0) {
        throw "Installer UI is missing required actions: $($Missing -join ', ')"
    }

    $Advanced = $Descendants | Where-Object {
        $_.Current.Name -eq '高级设置（可选）'
    } | Select-Object -First 1
    if (-not $Advanced) {
        throw 'Installer UI is missing the optional advanced settings expander.'
    }
    $Pattern = $null
    if (-not $Advanced.TryGetCurrentPattern(
        [System.Windows.Automation.ExpandCollapsePattern]::Pattern,
        [ref]$Pattern
    )) {
        throw 'Advanced settings does not expose the expand/collapse pattern.'
    }
    ([System.Windows.Automation.ExpandCollapsePattern]$Pattern).Expand()
    Start-Sleep -Milliseconds 300

    $ExpandedDescendants = $Root.FindAll(
        [System.Windows.Automation.TreeScope]::Descendants,
        [System.Windows.Automation.Condition]::TrueCondition
    )
    $TranscriptCheckBox = $ExpandedDescendants | Where-Object {
        $_.Current.ControlType -eq [System.Windows.Automation.ControlType]::CheckBox -and
        $_.Current.Name -eq '启用逐字稿增强版（实验性）'
    } | Select-Object -First 1
    if (-not $TranscriptCheckBox) {
        throw 'Expanded advanced settings is missing the transcript checkbox.'
    }

    $ExpectedWorkspace = Join-Path `
        ([Environment]::GetFolderPath('MyDocuments')) `
        '视知库助手'
    Wait-InstallerEnabled -Root $Root
    Invoke-InstallerButton -Root $Root -Name '复制工作区路径'
    $ClipboardDeadline = (Get-Date).AddSeconds(10)
    $ClipboardText = ''
    while ((Get-Date) -lt $ClipboardDeadline) {
        try {
            $ClipboardText = (Get-Clipboard -Raw).Trim()
        } catch {
            $ClipboardText = ''
        }
        if ($ClipboardText -eq $ExpectedWorkspace) {
            break
        }
        Start-Sleep -Milliseconds 200
    }
    if ($ClipboardText -ne $ExpectedWorkspace) {
        throw 'Copy-workspace action did not place the managed workspace path on the clipboard.'
    }
    Close-InstallerMessageBox `
        -ProcessId $Process.Id `
        -ExpectedText '工作区路径已复制'
    Wait-InstallerEnabled -Root $Root

    $Desktop = [Environment]::GetFolderPath('DesktopDirectory')
    $DesktopDiagnostic = Join-Path $Desktop '视知库诊断报告.json'
    Remove-Item -LiteralPath $DesktopDiagnostic -Force -ErrorAction SilentlyContinue
    Invoke-InstallerButton -Root $Root -Name '导出脱敏诊断报告'
    $DiagnosticDeadline = (Get-Date).AddSeconds(60)
    while (-not (Test-Path -LiteralPath $DesktopDiagnostic) -and
        (Get-Date) -lt $DiagnosticDeadline) {
        Start-Sleep -Milliseconds 250
    }
    if (-not (Test-Path -LiteralPath $DesktopDiagnostic)) {
        throw 'Export-diagnostics action did not create the desktop JSON report.'
    }
    $DiagnosticText = Get-Content -LiteralPath $DesktopDiagnostic -Raw
    $Diagnostic = $DiagnosticText | ConvertFrom-Json
    if ($Diagnostic.contains_secrets -or $Diagnostic.paid_call_performed) {
        throw 'Exported diagnostics reported a secret or paid call.'
    }
    if (
        $Diagnostic.support_status.contains_secrets -or
        $Diagnostic.support_status.contains_local_paths -or
        $Diagnostic.support_status.paid_call_performed
    ) {
        throw 'Exported support status is not safe to share.'
    }
    $ForbiddenDiagnosticPatterns = @(
        '(?i)api[_-]?key\s*[:=]',
        '(?i)bearer\s+[a-z0-9._-]+',
        '(?i)cookie\s*[:=]',
        '(?i)https?://[^\s"'']+[?&](token|sign|signature|auth_key)='
    )
    foreach ($Forbidden in $ForbiddenDiagnosticPatterns) {
        if ($DiagnosticText -match $Forbidden) {
            throw "Exported diagnostics matched a forbidden pattern: $Forbidden"
        }
    }
    $DiagnosticArtifact = Join-Path $ArtifactsDirectory 'windows-ui-diagnostics.json'
    Copy-Item -LiteralPath $DesktopDiagnostic -Destination $DiagnosticArtifact -Force
    Remove-Item -LiteralPath $DesktopDiagnostic -Force
    Close-InstallerMessageBox `
        -ProcessId $Process.Id `
        -ExpectedText '脱敏诊断报告已保存到桌面'

    $Report = [ordered]@{
        schema_version = 2
        ok = $true
        window_title = $Root.Current.Name
        required_button_count = $RequiredButtons.Count
        required_buttons = $RequiredButtons
        transcript_option = $TranscriptCheckBox.Current.Name
        copy_workspace_action = $true
        diagnostic_export_action = $true
        diagnostic_artifact = 'windows-ui-diagnostics.json'
        contains_secrets = $false
        contains_local_paths = $false
        paid_call_performed = $false
    }
    $Output = Join-Path $ArtifactsDirectory 'windows-ui-contract.json'
    $Report | ConvertTo-Json -Depth 5 | Set-Content $Output -Encoding utf8
    Write-Host 'Windows installer UI contract passed.'
} finally {
    if ($Process -and -not $Process.HasExited) {
        $null = $Process.CloseMainWindow()
        if (-not $Process.WaitForExit(5000)) {
            Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
