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

    $Report = [ordered]@{
        schema_version = 1
        ok = $true
        window_title = $Root.Current.Name
        required_button_count = $RequiredButtons.Count
        required_buttons = $RequiredButtons
        transcript_option = $TranscriptCheckBox.Current.Name
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
