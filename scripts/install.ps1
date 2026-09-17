[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$VaultPath,

    [ValidateSet('standard', 'transcript')]
    [string]$Profile = 'standard',

    [string]$PythonCommand = 'py',

    [string]$ZCodeConfig = "$HOME\.zcode\cli\config.json",

    [switch]$SkipZCode,

    [switch]$InstallApps,

    [switch]$SkipFirefoxProfile
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvRoot = Join-Path $RepoRoot '.venv'
$VenvPython = Join-Path $VenvRoot 'Scripts\python.exe'

function Refresh-ProcessPath {
    $MachinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $UserPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$MachinePath;$UserPath"
}

function Install-WingetPackage([string]$Id, [string]$Name) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "安装 $Name 需要 Windows 11 自带的 winget。请先从 Microsoft Store 更新‘应用安装程序’。"
    }
    Write-Host "安装或更新 $Name（$Id）..."
    & winget install --id $Id --exact --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw "$Name 安装失败（winget exit $LASTEXITCODE）。" }
}

function Find-Firefox {
    $Candidates = @(
        "$env:PROGRAMFILES\Mozilla Firefox\firefox.exe",
        "${env:PROGRAMFILES(X86)}\Mozilla Firefox\firefox.exe",
        "$env:LOCALAPPDATA\Mozilla Firefox\firefox.exe"
    )
    foreach ($Candidate in $Candidates) {
        if ($Candidate -and (Test-Path $Candidate -PathType Leaf)) { return $Candidate }
    }
    return $null
}

function Test-FirefoxProfile([string]$Name) {
    $ProfilesIni = Join-Path $env:APPDATA 'Mozilla\Firefox\profiles.ini'
    if (-not (Test-Path $ProfilesIni -PathType Leaf)) { return $false }
    return [bool](Select-String -Path $ProfilesIni -Pattern "^Name=$([regex]::Escape($Name))$" -CaseSensitive:$false -Quiet)
}

Write-Host 'Video to Obsidian alpha 安装：不会保存 API Key、Cookie 或修改现有 Obsidian 配置。'

if ($InstallApps) {
    Install-WingetPackage -Id 'Mozilla.Firefox' -Name 'Firefox'
    Install-WingetPackage -Id 'Obsidian.Obsidian' -Name 'Obsidian'
    Install-WingetPackage -Id 'Gyan.FFmpeg' -Name 'ffmpeg'
    Refresh-ProcessPath
}

if (-not (Test-Path $VenvPython -PathType Leaf)) {
    if ($PythonCommand -eq 'py') {
        if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
            throw '找不到 Python Launcher（py）。请先从 Python 官方渠道安装 Python 3.11+。'
        }
        & py -3.12 -m venv $VenvRoot
        if ($LASTEXITCODE -ne 0) {
            & py -3.11 -m venv $VenvRoot
        }
    }
    else {
        & $PythonCommand -m venv $VenvRoot
    }
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $VenvPython -PathType Leaf)) {
        throw '无法创建 Python 3.11+ 虚拟环境。请先从官方渠道安装 Python。'
    }
}

& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip 升级失败。' }

& $VenvPython -m pip install -e $RepoRoot
if ($LASTEXITCODE -ne 0) { throw 'Video to Obsidian 安装失败。' }

if (-not $SkipFirefoxProfile -and -not (Test-FirefoxProfile 'VideoToObsidian')) {
    $FirefoxExe = Find-Firefox
    if ($FirefoxExe) {
        Write-Host '创建专用 Firefox Profile：VideoToObsidian'
        & $FirefoxExe -CreateProfile 'VideoToObsidian'
        if ($LASTEXITCODE -ne 0) {
            Write-Warning 'Firefox Profile 自动创建失败；请关闭 Firefox 后运行 firefox.exe -P 手工创建。'
        }
    }
    else {
        Write-Warning '未找到 Firefox，无法创建专用 Profile。可使用 -InstallApps 自动安装后重试。'
    }
}

$InitArgs = @('-m', 'video_to_obsidian', 'init', '--vault', $VaultPath, '--profile', $Profile, '--reuse-existing')
& $VenvPython @InitArgs
if ($LASTEXITCODE -ne 0) { throw '公共配置初始化失败。已有配置时请先核对，不要直接覆盖。' }

if (-not $SkipZCode) {
    if (Test-Path $ZCodeConfig -PathType Leaf) {
        & $VenvPython -m video_to_obsidian configure-zcode --config $ZCodeConfig
        if ($LASTEXITCODE -ne 0) { throw 'ZCode MCP 配置失败。' }
    }
    else {
        Write-Warning "未找到 ZCode 配置：$ZCodeConfig；已跳过，安装 ZCode 后可单独运行 configure-zcode。"
    }
}

Write-Host ''
Write-Host 'Python 部分安装完成。下一步仍需要用户完成：'
Write-Host '1. 确认 Obsidian、Firefox、ffmpeg 和 ffprobe 已安装；yt-dlp 已随本项目安装。'
Write-Host '2. 在 Firefox 专用 Profile VideoToObsidian 中分别扫码登录抖音和B站。'
Write-Host '3. 亲自在终端运行 .venv\Scripts\video-to-obsidian.exe set-kimi-key。'
Write-Host '4. 用 Obsidian 打开所选 Vault，并按官方流程让 ZCode 连接微信。'
Write-Host '5. 重新运行 doctor；真实视频验收会产生 Kimi 费用，必须另行确认。'
Write-Host ''
& $VenvPython -m video_to_obsidian doctor --json
if ($LASTEXITCODE -ne 0) {
    Write-Warning '软件安装已完成，但人工配置尚未通过 doctor；本次不报告完整部署成功。'
    exit 2
}
exit 0
