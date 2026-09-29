using System.IO;
using System.Text.Json;

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

    private static string ConfigPath => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
        "VideoToObsidian",
        "config.toml"
    );

    public static string ConfiguredVaultPathOrDefault
    {
        get
        {
            var configured = ReadConfiguredString("vault_path");
            if (string.IsNullOrWhiteSpace(configured))
            {
                return DefaultVaultPath;
            }
            try
            {
                return Path.GetFullPath(configured);
            }
            catch (Exception exception) when (
                exception is ArgumentException
                or NotSupportedException
                or PathTooLongException
            )
            {
                return DefaultVaultPath;
            }
        }
    }

    public static bool HasConfiguration => File.Exists(ConfigPath);

    public static string ConfiguredProfileOrDefault
    {
        get
        {
            var configured = ReadConfiguredString("profile");
            return configured is "standard" or "transcript" ? configured : "standard";
        }
    }

    public bool IsInstalled => _installation.IsInstalled;

    public async Task PrepareAsync(
        string vaultPath,
        string workspacePath,
        string profile,
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
        if (profile is not ("standard" or "transcript"))
        {
            throw new InvalidOperationException("分析档位只能是标准版或逐字稿增强版。");
        }

        var normalizedVault = Path.GetFullPath(vaultPath.Trim());
        var normalizedWorkspace = Path.GetFullPath(workspacePath.Trim());
        if (
            HasConfiguration
            && !string.Equals(
                Path.GetFullPath(ConfiguredVaultPathOrDefault),
                normalizedVault,
                StringComparison.OrdinalIgnoreCase
            )
        )
        {
            throw new InvalidOperationException(
                "本机已有视知库配置；修复必须继续使用原知识库目录，避免把笔记拆到两个位置。"
            );
        }
        await _installation.EnsureInstalledAsync(report);

        if (HasConfiguration && ConfiguredProfileOrDefault != profile)
        {
            report("正在安全切换分析档位…");
            await _backend.RunJsonAsync(
                new[] { "set-profile", "--profile", profile, "--json" }
            );
        }

        report("正在创建 Obsidian 知识库…");
        await _backend.RunAsync(
            new[]
            {
                "init",
                "--vault",
                normalizedVault,
                "--profile",
                profile,
                "--reuse-existing",
            }
        );

        report("正在创建微信助手专用工作区…");
        await _backend.RunJsonAsync(
            new[] { "bootstrap-workspace", "--workspace", normalizedWorkspace, "--json" }
        );
    }

    private static string? ReadConfiguredString(string key)
    {
        if (!File.Exists(ConfigPath))
        {
            return null;
        }
        try
        {
            var prefix = key + " = ";
            var line = File.ReadLines(ConfigPath)
                .FirstOrDefault(candidate => candidate.StartsWith(prefix, StringComparison.Ordinal));
            if (line is null)
            {
                return null;
            }
            return JsonSerializer.Deserialize<string>(line[prefix.Length..]);
        }
        catch (Exception exception) when (
            exception is IOException
            or UnauthorizedAccessException
            or JsonException
            or ArgumentException
            or NotSupportedException
        )
        {
            return null;
        }
    }
}
