using System.IO;

namespace VideoToObsidian.Setup;

internal sealed class MachinePreparationClient
{
    private readonly InstallationClient _installation = new();
    private readonly BackendClient _backend = new();

    public static string DefaultVaultPath
    {
        get
        {
            var documents = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);
            return Path.Combine(documents, "视知库");
        }
    }

    public static string DefaultWorkspacePath
    {
        get
        {
            var documents = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);
            return Path.Combine(documents, "视知库助手");
        }
    }

    public bool IsInstalled => _installation.IsInstalled;

    public async Task PrepareAsync(
        string vaultPath,
        string workspacePath,
        Action<string> report
    )
    {
        if (string.IsNullOrWhiteSpace(vaultPath))
        {
            throw new InvalidOperationException("请选择 Obsidian 知识库目录。");
        }
        if (string.IsNullOrWhiteSpace(workspacePath))
        {
            throw new InvalidOperationException("无法确定视知库助手工作区目录。");
        }

        var normalizedVault = Path.GetFullPath(vaultPath.Trim());
        var normalizedWorkspace = Path.GetFullPath(workspacePath.Trim());
        await _installation.EnsureInstalledAsync(report);

        report("正在创建 Obsidian 知识库…");
        await _backend.RunAsync(
            new[] { "init", "--vault", normalizedVault, "--reuse-existing" }
        );

        report("正在创建微信助手专用工作区…");
        await _backend.RunJsonAsync(
            new[] { "bootstrap-workspace", "--workspace", normalizedWorkspace, "--json" }
        );
    }
}
