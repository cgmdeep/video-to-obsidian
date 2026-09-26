[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [string]$ZCodeConfig = "$HOME\.zcode\cli\config.json",
    [string]$WorkspacePath = ([IO.Path]::Combine([Environment]::GetFolderPath('MyDocuments'), '视知库助手')),
    [switch]$RemovePrivateData
)

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Split-Path -Parent $PSScriptRoot)).Path
$VenvRoot = Join-Path $RepoRoot '.venv'
$InstalledRoot = Join-Path $env:LOCALAPPDATA 'VideoToObsidian'
$InstalledRuntime = Join-Path $InstalledRoot 'runtime'
$InstalledCli = Join-Path $InstalledRuntime 'Scripts\video-to-obsidian.exe'
$RepoCli = Join-Path $VenvRoot 'Scripts\video-to-obsidian.exe'
$Cli = if (Test-Path $InstalledCli -PathType Leaf) { $InstalledCli } elseif (Test-Path $RepoCli -PathType Leaf) { $RepoCli } else { $null }
$WorkspaceConfig = Join-Path $WorkspacePath '.zcode\config.json'
$ConfigPaths = @($ZCodeConfig, $WorkspaceConfig) | Select-Object -Unique

if (-not $Cli -and ($ConfigPaths | Where-Object { Test-Path $_ -PathType Leaf })) {
    throw '未找到视知库核心，无法安全编辑现有 ZCode 配置；请先修复安装后再卸载。'
}

foreach ($ConfigPath in $ConfigPaths) {
    if ((Test-Path $ConfigPath -PathType Leaf) -and $Cli) {
        & $Cli unconfigure-zcode --config $ConfigPath
        if ($LASTEXITCODE -ne 0) { throw "无法安全移除 ZCode MCP 条目，已停止卸载：$ConfigPath" }
    }
}

if ($RemovePrivateData -and $Cli) {
    & $Cli delete-kimi-key
    if ($LASTEXITCODE -ne 0) { throw '无法安全删除系统钥匙串中的 Kimi Key，已停止私有数据清理。' }
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

foreach ($ManagedInstallPath in @(
    $InstalledRuntime,
    (Join-Path $InstalledRoot 'payload')
) | Select-Object -Unique) {
    if ($ManagedInstallPath -and (Test-Path $ManagedInstallPath -PathType Container)) {
        $ResolvedPath = (Resolve-Path $ManagedInstallPath).Path
        $ResolvedRoot = (Resolve-Path $InstalledRoot).Path
        if (-not $ResolvedPath.StartsWith($ResolvedRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
            throw "安装目录越过应用边界，拒绝删除：$ResolvedPath"
        }
        if ($PSCmdlet.ShouldProcess($ResolvedPath, '删除图形安装器部署的核心组件')) {
            Remove-Item -LiteralPath $ResolvedPath -Recurse -Force
        }
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

Write-Host '卸载完成。Obsidian Vault、视知库助手工作区、Firefox Profile 和已安装的第三方软件均未删除。'
if (-not $RemovePrivateData) {
    Write-Host 'Kimi Key、检查点和私有运行数据已保留；如需删除，请重新运行并显式添加 -RemovePrivateData。'
}
