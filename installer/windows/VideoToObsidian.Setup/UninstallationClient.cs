using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.Json;

namespace VideoToObsidian.Setup;

internal sealed class UninstallationClient
{
    private const string ManagedServerName = "video-to-obsidian";
    private readonly string _localRoot = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "VideoToObsidian"
    );
    private readonly string _roamingRoot = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
        "VideoToObsidian"
    );

    private string CoreExecutable => Path.Combine(
        _localRoot,
        "runtime",
        "Scripts",
        "video-to-obsidian.exe"
    );

    public async Task<UninstallationResult> UninstallAsync(
        string workspacePath,
        bool removePrivateData,
        Action<string> report
    )
    {
        var normalizedWorkspace = Path.GetFullPath(workspacePath);
        var configuredVaultPath = MachinePreparationClient.ConfiguredVaultPathOrDefault;
        var vaultExistedBefore = Directory.Exists(configuredVaultPath);
        var workspaceExistedBefore = Directory.Exists(normalizedWorkspace);
        var firefoxProfileExistedBefore = FirefoxProfileExists();
        var globalConfig = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
            ".zcode",
            "cli",
            "config.json"
        );
        var workspaceConfig = Path.Combine(normalizedWorkspace, ".zcode", "config.json");
        var configs = new[] { globalConfig, workspaceConfig }
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray();
        var managedConfigs = configs.Where(HasManagedServer).ToArray();

        if (managedConfigs.Length > 0 && !File.Exists(CoreExecutable))
        {
            throw new UninstallationSafetyException(
                "检测到视知库 MCP，但核心组件缺失。为避免误改 ZCode，请先修复安装后再卸载。"
            );
        }

        foreach (var config in managedConfigs)
        {
            report("正在从 ZCode 安全移除视知库连接…");
            await RunCoreAsync(new[] { "unconfigure-zcode", "--config", config });
            if (HasManagedServer(config))
            {
                throw new UninstallationSafetyException(
                    $"未能验证 ZCode 配置已清理，已停止卸载：{config}"
                );
            }
        }

        if (removePrivateData && File.Exists(CoreExecutable))
        {
            report("正在删除系统安全存储中的 Kimi Key…");
            await RunCoreAsync(new[] { "delete-kimi-key" });
        }

        report("正在移除视知库核心组件…");
        await DeleteDirectoryWithRetryAsync(Path.Combine(_localRoot, "runtime"));
        await DeleteDirectoryWithRetryAsync(Path.Combine(_localRoot, "payload"));

        if (removePrivateData)
        {
            report("正在删除视知库私有配置和检查点…");
            await DeleteDirectoryWithRetryAsync(_roamingRoot);
            await DeleteDirectoryWithRetryAsync(_localRoot);
        }

        return new UninstallationResult(
            CoreRemoved: !File.Exists(CoreExecutable),
            ManagedMcpRemoved: configs.All(path => !HasManagedServer(path)),
            VaultPreserved: vaultExistedBefore
                == Directory.Exists(configuredVaultPath),
            WorkspacePreserved: workspaceExistedBefore == Directory.Exists(normalizedWorkspace),
            FirefoxProfilePreserved: firefoxProfileExistedBefore == FirefoxProfileExists(),
            PrivateDataRemoved: removePrivateData
                && !Directory.Exists(_roamingRoot)
                && !Directory.Exists(_localRoot)
        );
    }

    private static bool HasManagedServer(string configPath)
    {
        if (!File.Exists(configPath))
        {
            return false;
        }
        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(configPath));
            return document.RootElement.TryGetProperty("mcp", out var mcp)
                && mcp.ValueKind == JsonValueKind.Object
                && mcp.TryGetProperty("servers", out var servers)
                && servers.ValueKind == JsonValueKind.Object
                && servers.TryGetProperty(ManagedServerName, out _);
        }
        catch (JsonException exception)
        {
            throw new UninstallationSafetyException(
                $"ZCode 配置无法解析，拒绝继续卸载：{configPath}",
                exception
            );
        }
    }

    private async Task RunCoreAsync(IEnumerable<string> arguments)
    {
        var start = new ProcessStartInfo
        {
            FileName = CoreExecutable,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
            CreateNoWindow = true,
        };
        start.Environment["PYTHONUTF8"] = "1";
        start.Environment["PYTHONIOENCODING"] = "utf-8";
        foreach (var argument in arguments)
        {
            start.ArgumentList.Add(argument);
        }
        using var process = new Process { StartInfo = start };
        process.Start();
        var stdout = process.StandardOutput.ReadToEndAsync();
        var stderr = process.StandardError.ReadToEndAsync();
        using var cancellation = new CancellationTokenSource(TimeSpan.FromMinutes(2));
        try
        {
            await process.WaitForExitAsync(cancellation.Token);
        }
        catch (OperationCanceledException)
        {
            process.Kill(entireProcessTree: true);
            await process.WaitForExitAsync();
            throw new UninstallationSafetyException("卸载辅助命令超时，已停止并保留数据。");
        }
        var output = await stdout;
        var error = await stderr;
        if (process.ExitCode != 0)
        {
            var detail = string.IsNullOrWhiteSpace(output) ? error : output;
            throw new UninstallationSafetyException(
                string.IsNullOrWhiteSpace(detail) ? "卸载辅助命令执行失败。" : detail.Trim()
            );
        }
    }

    private static async Task DeleteDirectoryWithRetryAsync(string path)
    {
        if (!Directory.Exists(path))
        {
            return;
        }
        Exception? lastError = null;
        for (var attempt = 0; attempt < 5; attempt++)
        {
            try
            {
                Directory.Delete(path, recursive: true);
                return;
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
                lastError = exception;
                await Task.Delay(TimeSpan.FromMilliseconds(250 * (attempt + 1)));
            }
        }
        throw new UninstallationSafetyException($"无法安全删除受管目录：{path}", lastError);
    }

    private static bool FirefoxProfileExists()
    {
        var profiles = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "Mozilla",
            "Firefox",
            "profiles.ini"
        );
        return File.Exists(profiles)
            && File.ReadAllText(profiles).Contains(
                "Name=VideoToObsidian",
                StringComparison.OrdinalIgnoreCase
            );
    }
}

internal sealed record UninstallationResult(
    bool CoreRemoved,
    bool ManagedMcpRemoved,
    bool VaultPreserved,
    bool WorkspacePreserved,
    bool FirefoxProfilePreserved,
    bool PrivateDataRemoved
);

internal sealed class UninstallationSafetyException : Exception
{
    public UninstallationSafetyException(string message, Exception? innerException = null)
        : base(message, innerException) { }
}
