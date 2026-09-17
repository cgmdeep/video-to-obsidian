[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [string]$ZCodeConfig = "$HOME\.zcode\cli\config.json",
    [switch]$RemovePrivateData
)

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Split-Path -Parent $PSScriptRoot)).Path
$VenvRoot = Join-Path $RepoRoot '.venv'
$VenvPython = Join-Path $VenvRoot 'Scripts\python.exe'

if ((Test-Path $ZCodeConfig -PathType Leaf) -and (Test-Path $VenvPython -PathType Leaf)) {
    & $VenvPython -m video_to_obsidian unconfigure-zcode --config $ZCodeConfig
    if ($LASTEXITCODE -ne 0) { throw '无法安全移除 ZCode MCP 条目，已停止卸载。' }
}

if (Test-Path $VenvRoot -PathType Container) {
    $ResolvedVenv = (Resolve-Path $VenvRoot).Path
    if ((Split-Path -Parent $ResolvedVenv) -ne $RepoRoot -or (Split-Path -Leaf $ResolvedVenv) -ne '.venv') {
        throw "虚拟环境路径越过仓库边界，拒绝删除：$ResolvedVenv"
    }
    if ($PSCmdlet.ShouldProcess($ResolvedVenv, '删除项目虚拟环境')) {
        Remove-Item -LiteralPath $ResolvedVenv -Recurse -Force
    }
}

if ($RemovePrivateData) {
    $PrivateRoots = @(
        (Join-Path $env:APPDATA 'VideoToObsidian'),
        (Join-Path $env:LOCALAPPDATA 'VideoToObsidian')
    ) | Select-Object -Unique
    foreach ($Root in $PrivateRoots) {
        if ($Root -and (Test-Path $Root -PathType Container)) {
            if ($PSCmdlet.ShouldProcess($Root, '删除私有配置、检查点、候选笔记与视频归档')) {
                Remove-Item -LiteralPath $Root -Recurse -Force
            }
        }
    }
}

Write-Host '卸载完成。Obsidian Vault、Firefox Profile 和已安装的第三方软件均未删除。'
if (-not $RemovePrivateData) {
    Write-Host '私有运行数据已保留；如需删除，请重新运行并显式添加 -RemovePrivateData。'
}
