using System.IO;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace VideoToObsidian.Setup;

internal static class ObsidianVaultRegistry
{
    public static string EnsureRegistered(string vaultPath)
    {
        var normalizedVault = Path.TrimEndingDirectorySeparator(
            Path.GetFullPath(vaultPath.Trim())
        );
        if (!Directory.Exists(normalizedVault))
        {
            throw new DirectoryNotFoundException("知识库目录不存在。");
        }

        var roaming = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
        var configDirectory = Path.Combine(roaming, "obsidian");
        var configPath = Path.Combine(configDirectory, "obsidian.json");
        Directory.CreateDirectory(configDirectory);

        DateTime? originalWriteTime = null;
        JsonObject root;
        if (File.Exists(configPath))
        {
            originalWriteTime = File.GetLastWriteTimeUtc(configPath);
            var text = File.ReadAllText(configPath, Encoding.UTF8);
            root = JsonNode.Parse(text) as JsonObject
                ?? throw new InvalidDataException("Obsidian 配置格式无法识别。");
        }
        else
        {
            root = new JsonObject();
        }

        JsonObject vaults;
        if (root["vaults"] is null)
        {
            vaults = new JsonObject();
            root["vaults"] = vaults;
        }
        else
        {
            vaults = root["vaults"] as JsonObject
                ?? throw new InvalidDataException("Obsidian Vault 配置格式无法识别。");
        }

        foreach (var entry in vaults)
        {
            if (entry.Value is not JsonObject value)
            {
                continue;
            }
            var existingPath = value["path"] is JsonValue pathValue
                && pathValue.TryGetValue<string>(out var parsedPath)
                    ? parsedPath
                    : null;
            if (
                !string.IsNullOrWhiteSpace(existingPath)
                && PathsEqual(existingPath, normalizedVault)
            )
            {
                return entry.Key;
            }
        }

        var vaultId = CreateVaultId(vaults);
        vaults[vaultId] = new JsonObject
        {
            ["path"] = normalizedVault,
            ["ts"] = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
            ["open"] = true,
        };

        var temporaryPath = Path.Combine(
            configDirectory,
            $"obsidian.video-to-obsidian.{Guid.NewGuid():N}.tmp"
        );
        try
        {
            var json = root.ToJsonString(new JsonSerializerOptions { WriteIndented = false });
            File.WriteAllText(temporaryPath, json, new UTF8Encoding(false));
            if (originalWriteTime.HasValue)
            {
                if (
                    !File.Exists(configPath)
                    || File.GetLastWriteTimeUtc(configPath) != originalWriteTime.Value
                )
                {
                    throw new IOException("Obsidian 配置刚被其他进程修改，请重试。");
                }
                File.Replace(
                    temporaryPath,
                    configPath,
                    configPath + ".video-to-obsidian.bak",
                    ignoreMetadataErrors: true
                );
            }
            else
            {
                File.Move(temporaryPath, configPath);
            }
        }
        finally
        {
            if (File.Exists(temporaryPath))
            {
                File.Delete(temporaryPath);
            }
        }
        return vaultId;
    }

    private static bool PathsEqual(string left, string right)
    {
        try
        {
            return string.Equals(
                Path.TrimEndingDirectorySeparator(Path.GetFullPath(left)),
                Path.TrimEndingDirectorySeparator(Path.GetFullPath(right)),
                StringComparison.OrdinalIgnoreCase
            );
        }
        catch (Exception exception) when (
            exception is ArgumentException
            or NotSupportedException
            or PathTooLongException
        )
        {
            return false;
        }
    }

    private static string CreateVaultId(JsonObject vaults)
    {
        while (true)
        {
            var candidate = Guid.NewGuid().ToString("N")[..16];
            if (!vaults.ContainsKey(candidate))
            {
                return candidate;
            }
        }
    }
}
