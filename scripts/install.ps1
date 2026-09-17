[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$VaultPath,

    [ValidateSet('standard', 'transcript')]
    [string]$Profile = 'standard',

    [string]$PythonCommand = 'py',

    [string]$ZCodeConfig = "$HOME\.zcode\cli\config.json",

    [switch]$SkipZCode
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvRoot = Join-Path $RepoRoot '.venv'
$VenvPython = Join-Path $VenvRoot 'Scripts\python.exe'

Write-Host 'Video to Obsidian alpha 安装：只安装 Python 包，不会保存 API Key 或 Cookie。'

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

$InitArgs = @('-m', 'video_to_obsidian', 'init', '--vault', $VaultPath, '--profile', $Profile)
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
Write-Host '1. 确认 Obsidian、Firefox、ffmpeg、ffprobe、yt-dlp 已安装。'
Write-Host '2. 在 Firefox 专用 Profile VideoToObsidian 中扫码登录抖音和B站。'
Write-Host '3. 亲自在终端运行 .venv\Scripts\video-to-obsidian.exe set-kimi-key。'
Write-Host '4. 运行 doctor；真实视频验收会产生 Kimi 费用，必须另行确认。'
Write-Host ''
& $VenvPython -m video_to_obsidian doctor --json
if ($LASTEXITCODE -ne 0) {
    Write-Warning 'Python 部分已完成，但 doctor 尚未全部通过；请完成上述人工步骤后重新运行。'
}
exit 0
