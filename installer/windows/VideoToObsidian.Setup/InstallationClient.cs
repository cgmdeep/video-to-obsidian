using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Net.Http;
using System.Reflection;
using System.Security.Cryptography;
using System.Text.Json;

namespace VideoToObsidian.Setup;

internal sealed class InstallationClient
{
    private readonly string _appRoot = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "VideoToObsidian"
    );

    public string CoreExecutable => Path.Combine(
        _appRoot,
        "runtime",
        "Scripts",
        "video-to-obsidian.exe"
    );

    public bool IsInstalled => File.Exists(CoreExecutable);

    public async Task EnsureInstalledAsync(Action<string> report)
    {
        Directory.CreateDirectory(_appRoot);
        var winget = await ResolveWingetAsync();
        var runtimePython = Path.Combine(_appRoot, "runtime", "Scripts", "python.exe");
        if (!File.Exists(runtimePython))
        {
            var python = await EnsurePythonAsync(winget, report);
            report("正在创建独立运行环境…");
            await RunCheckedAsync(
                python,
                new[] { "-m", "venv", Path.Combine(_appRoot, "runtime") }
            );
        }

        var wheel = ExtractEmbeddedWheel();
        var wheelHash = ComputeSha256(wheel);
        var marker = Path.Combine(_appRoot, "runtime", ".embedded-wheel.sha256");
        var installedHash = File.Exists(marker) ? File.ReadAllText(marker).Trim() : "";
        if (!File.Exists(CoreExecutable)
            || !string.Equals(installedHash, wheelHash, StringComparison.OrdinalIgnoreCase))
        {
            report(File.Exists(CoreExecutable)
                ? "正在升级视知库核心及下载组件…"
                : "正在安装视知库核心及下载组件…");
            await RunCheckedAsync(
                runtimePython,
                new[]
                {
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "--upgrade",
                    "--force-reinstall",
                    wheel,
                },
                TimeSpan.FromMinutes(10)
            );
            await File.WriteAllTextAsync(marker, wheelHash + Environment.NewLine);
        }
        else
        {
            report("视知库核心已是当前版本，正在校验完整性。");
        }

        if (!File.Exists(CoreExecutable))
        {
            throw new InvalidOperationException("核心组件安装后未找到可执行文件。");
        }
        await RunCheckedAsync(
            runtimePython,
            new[] { "-c", "import video_to_obsidian, selenium" }
        );
        await RunCheckedAsync(runtimePython, new[] { "-m", "pip", "check" });

        await EnsureFirefoxAsync(winget, report);
        await EnsureObsidianAsync(winget, report);
        await EnsureWingetPackageAsync(
            winget,
            "Gyan.FFmpeg.Essentials",
            "ffmpeg 精简组件",
            report,
            TimeSpan.FromMinutes(30)
        );
        await EnsureFirefoxProfileAsync(report);
    }

    private async Task<string> EnsurePythonAsync(string winget, Action<string> report)
    {
        var discovered = await DiscoverPythonAsync();
        if (discovered is not null)
        {
            return discovered;
        }
        report("未发现 Python，正通过 Windows 官方软件源安装…");
        await RunCheckedAsync(
            winget,
            new[]
            {
                "install",
                "--id",
                "Python.Python.3.12",
                "--exact",
                "--silent",
                "--accept-package-agreements",
                "--accept-source-agreements",
            }
        );
        discovered = await DiscoverPythonAsync();
        if (discovered is not null)
        {
            return discovered;
        }
        var conventional = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "Programs",
            "Python",
            "Python312",
            "python.exe"
        );
        if (File.Exists(conventional))
        {
            return conventional;
        }
        throw new InvalidOperationException(
            "Python 安装完成后仍无法定位。请重启本向导后再试。"
        );
    }

    private static async Task<string?> DiscoverPythonAsync()
    {
        foreach (var version in new[] { "-3.12", "-3.11" })
        {
            var result = await TryCaptureAsync(
                "py",
                new[] { version, "-c", "import sys; print(sys.executable)" },
                TimeSpan.FromSeconds(30)
            );
            if (result.ExitCode == 0)
            {
                var candidate = result.Stdout.Trim();
                if (File.Exists(candidate))
                {
                    return candidate;
                }
            }
        }
        return null;
    }

    private string ExtractEmbeddedWheel()
    {
        var assembly = Assembly.GetExecutingAssembly();
        var resourceName = assembly
            .GetManifestResourceNames()
            .SingleOrDefault(name => name.StartsWith("Payload/", StringComparison.Ordinal)
                && name.EndsWith(".whl", StringComparison.OrdinalIgnoreCase));
        if (resourceName is null)
        {
            throw new InvalidOperationException("安装包中缺少视知库核心 wheel。");
        }
        var payloadDirectory = Path.Combine(_appRoot, "payload");
        Directory.CreateDirectory(payloadDirectory);
        var wheelName = resourceName["Payload/".Length..];
        var destination = Path.Combine(payloadDirectory, wheelName);
        using var source = assembly.GetManifestResourceStream(resourceName)
            ?? throw new InvalidOperationException("无法读取内嵌的核心 wheel。");
        using var target = File.Create(destination);
        source.CopyTo(target);
        return destination;
    }

    internal static void WriteEmbeddedWheelVerification(string destination)
    {
        var assembly = Assembly.GetExecutingAssembly();
        var resources = assembly.GetManifestResourceNames()
            .Where(name => name.StartsWith("Payload/", StringComparison.Ordinal)
                && name.EndsWith(".whl", StringComparison.OrdinalIgnoreCase))
            .ToArray();
        if (resources.Length != 1)
        {
            throw new InvalidOperationException(
                $"安装包应内嵌 1 个 wheel，实际为 {resources.Length} 个。"
            );
        }
        using var stream = assembly.GetManifestResourceStream(resources[0])
            ?? throw new InvalidOperationException("无法读取内嵌的核心 wheel。");
        using var memory = new MemoryStream();
        stream.CopyTo(memory);
        var bytes = memory.ToArray();
        memory.Position = 0;
        using var archive = new ZipArchive(memory, ZipArchiveMode.Read, leaveOpen: true);
        var metadataEntry = archive.Entries.SingleOrDefault(entry =>
            entry.FullName.EndsWith(".dist-info/METADATA", StringComparison.OrdinalIgnoreCase)
        ) ?? throw new InvalidOperationException("wheel 缺少 METADATA。");
        using var reader = new StreamReader(metadataEntry.Open());
        var metadata = reader.ReadToEnd();
        var hasSelenium = metadata.Split('\n').Any(line =>
            line.StartsWith("Requires-Dist: selenium", StringComparison.OrdinalIgnoreCase)
        );
        if (!hasSelenium)
        {
            throw new InvalidOperationException("内嵌 wheel 缺少 Selenium 依赖。");
        }
        var report = new
        {
            schema_version = 1,
            resource = resources[0],
            sha256 = Convert.ToHexString(SHA256.HashData(bytes)),
            has_selenium = true,
            contains_secrets = false,
        };
        var parent = Path.GetDirectoryName(Path.GetFullPath(destination));
        if (!string.IsNullOrWhiteSpace(parent))
        {
            Directory.CreateDirectory(parent);
        }
        File.WriteAllText(
            destination,
            JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true })
        );
    }

    private static string ComputeSha256(string path)
    {
        using var stream = File.OpenRead(path);
        return Convert.ToHexString(SHA256.HashData(stream));
    }

    private static async Task EnsureWingetPackageAsync(
        string winget,
        string id,
        string displayName,
        Action<string> report,
        TimeSpan? installTimeout = null
    )
    {
        report($"正在检查 {displayName}…");
        var list = await TryCaptureAsync(
            winget,
            new[] { "list", "--id", id, "--exact" },
            TimeSpan.FromMinutes(2)
        );
        if (list.ExitCode == 0 && list.Stdout.Contains(id, StringComparison.OrdinalIgnoreCase))
        {
            return;
        }
        report($"正在安装 {displayName}…");
        await RunCheckedAsync(
            winget,
            new[]
            {
                "install",
                "--id",
                id,
                "--exact",
                "--silent",
                "--accept-package-agreements",
                "--accept-source-agreements",
            },
            installTimeout ?? TimeSpan.FromMinutes(10)
        );
    }

    private static async Task EnsureFirefoxAsync(string winget, Action<string> report)
    {
        if (FindFirefoxExecutable() is not null)
        {
            return;
        }

        report("正在检查 Firefox…");
        var list = await TryCaptureAsync(
            winget,
            new[] { "list", "--id", "Mozilla.Firefox", "--exact" },
            TimeSpan.FromMinutes(2)
        );
        if (list.ExitCode == 0
            && list.Stdout.Contains("Mozilla.Firefox", StringComparison.OrdinalIgnoreCase)
            && FindFirefoxExecutable() is not null)
        {
            return;
        }

        report("正在安装 Firefox…");
        var installArguments = new[]
        {
            "install",
            "--id",
            "Mozilla.Firefox",
            "--exact",
            "--source",
            "winget",
            "--silent",
            "--accept-package-agreements",
            "--accept-source-agreements",
        };
        var install = await TryCaptureAsync(
            winget,
            installArguments,
            TimeSpan.FromMinutes(10)
        );
        if (install.ExitCode != 0 || FindFirefoxExecutable() is null)
        {
            report("Windows 软件源暂时不可用，正在刷新后重试 Firefox…");
            await TryCaptureAsync(
                winget,
                new[] { "source", "update", "--name", "winget" },
                TimeSpan.FromMinutes(3)
            );
            install = await TryCaptureAsync(
                winget,
                installArguments,
                TimeSpan.FromMinutes(10)
            );
        }
        if (install.ExitCode == 0 && FindFirefoxExecutable() is not null)
        {
            return;
        }

        report("Windows 软件源仍不可用，正在从 Mozilla 官方下载 Firefox…");
        var installer = Path.Combine(
            Path.GetTempPath(),
            $"VideoToObsidian-Firefox-{Guid.NewGuid():N}.exe"
        );
        try
        {
            using var http = new HttpClient { Timeout = TimeSpan.FromMinutes(10) };
            using var response = await http.GetAsync(
                "https://download.mozilla.org/?product=firefox-latest-ssl&os=win64&lang=zh-CN",
                HttpCompletionOption.ResponseHeadersRead
            );
            response.EnsureSuccessStatusCode();
            await using (var source = await response.Content.ReadAsStreamAsync())
            await using (var target = File.Create(installer))
            {
                await source.CopyToAsync(target);
            }
            await RunCheckedAsync(
                installer,
                new[] { "-ms" },
                TimeSpan.FromMinutes(10)
            );
        }
        finally
        {
            try
            {
                File.Delete(installer);
            }
            catch
            {
                // The OS may still hold the installer briefly; leaving a temp file is safer
                // than turning an otherwise successful installation into a failure.
            }
        }

        if (FindFirefoxExecutable() is null)
        {
            var detail = string.IsNullOrWhiteSpace(install.Stderr)
                ? install.Stdout
                : install.Stderr;
            throw new InvalidOperationException(
                string.IsNullOrWhiteSpace(detail)
                    ? "Firefox 安装完成后仍无法定位。"
                    : $"Firefox 安装完成后仍无法定位。Windows 软件源最后返回：{detail.Trim()}"
            );
        }
    }

    private static async Task EnsureObsidianAsync(string winget, Action<string> report)
    {
        report("正在检查 Obsidian…");
        foreach (var id in new[] { "XP8K51FR765RLD", "Obsidian.Obsidian" })
        {
            var list = await TryCaptureAsync(
                winget,
                new[] { "list", "--id", id, "--exact" },
                TimeSpan.FromMinutes(2)
            );
            if (list.ExitCode == 0 && list.Stdout.Contains(id, StringComparison.OrdinalIgnoreCase))
            {
                return;
            }
        }

        report("正在通过 Microsoft Store 安装 Obsidian…");
        await RunCheckedAsync(
            winget,
            new[]
            {
                "install",
                "--id",
                "XP8K51FR765RLD",
                "--exact",
                "--source",
                "msstore",
                "--silent",
                "--accept-package-agreements",
                "--accept-source-agreements",
            },
            TimeSpan.FromMinutes(10)
        );
    }

    private static async Task<string> ResolveWingetAsync()
    {
        var direct = await TryCaptureAsync(
            "winget",
            new[] { "--version" },
            TimeSpan.FromSeconds(30)
        );
        if (direct.ExitCode == 0)
        {
            return "winget";
        }

        var alias = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "Microsoft",
            "WindowsApps",
            "winget.exe"
        );
        if (await IsWorkingWingetAsync(alias))
        {
            return alias;
        }

        var powershell = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.System),
            "WindowsPowerShell",
            "v1.0",
            "powershell.exe"
        );
        var package = await TryCaptureAsync(
            powershell,
            new[]
            {
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Get-AppxPackage Microsoft.DesktopAppInstaller | "
                    + "Sort-Object Version -Descending | "
                    + "Select-Object -First 1 -ExpandProperty InstallLocation",
            },
            TimeSpan.FromSeconds(30)
        );
        if (package.ExitCode == 0 && !string.IsNullOrWhiteSpace(package.Stdout))
        {
            var packagedWinget = Path.Combine(package.Stdout.Trim(), "winget.exe");
            if (await IsWorkingWingetAsync(packagedWinget))
            {
                return packagedWinget;
            }
        }

        throw new InvalidOperationException(
            "Windows 应用安装程序（winget）尚未可用。请先在 Microsoft Store 更新“应用安装程序”，然后重新打开本向导。"
        );
    }

    private static async Task<bool> IsWorkingWingetAsync(string path)
    {
        if (!File.Exists(path))
        {
            return false;
        }
        var result = await TryCaptureAsync(
            path,
            new[] { "--version" },
            TimeSpan.FromSeconds(30)
        );
        return result.ExitCode == 0;
    }

    private static async Task EnsureFirefoxProfileAsync(Action<string> report)
    {
        var profiles = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "Mozilla",
            "Firefox",
            "profiles.ini"
        );
        if (File.Exists(profiles)
            && File.ReadAllText(profiles).Contains("Name=VideoToObsidian", StringComparison.OrdinalIgnoreCase))
        {
            return;
        }
        var firefox = FindFirefoxExecutable();
        if (firefox is null)
        {
            throw new InvalidOperationException("Firefox 已安装但未找到可执行文件。");
        }
        report("正在创建视知库专用登录空间…");
        await RunCheckedAsync(
            firefox,
            new[] { "-CreateProfile", "VideoToObsidian" },
            TimeSpan.FromMinutes(2)
        );
    }

    private static string? FindFirefoxExecutable()
    {
        var candidates = new[]
        {
            Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
                "Mozilla Firefox",
                "firefox.exe"
            ),
            Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86),
                "Mozilla Firefox",
                "firefox.exe"
            ),
            Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "Mozilla Firefox",
                "firefox.exe"
            ),
        };
        return candidates.FirstOrDefault(File.Exists);
    }

    private static async Task RunCheckedAsync(
        string executable,
        IEnumerable<string> arguments,
        TimeSpan? timeout = null
    )
    {
        var result = await TryCaptureAsync(executable, arguments, timeout);
        if (result.TimedOut)
        {
            throw new InvalidOperationException(
                $"运行 {executable} 超时，已停止该安装步骤。"
            );
        }
        if (result.ExitCode != 0)
        {
            var detail = string.IsNullOrWhiteSpace(result.Stderr)
                ? result.Stdout
                : result.Stderr;
            throw new InvalidOperationException(
                string.IsNullOrWhiteSpace(detail)
                    ? $"运行 {executable} 失败（{result.ExitCode}）。"
                    : detail.Trim()
            );
        }
    }

    private static async Task<ProcessResult> TryCaptureAsync(
        string executable,
        IEnumerable<string> arguments,
        TimeSpan? timeout = null
    )
    {
        var start = new ProcessStartInfo
        {
            FileName = executable,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            StandardOutputEncoding = System.Text.Encoding.UTF8,
            StandardErrorEncoding = System.Text.Encoding.UTF8,
            CreateNoWindow = true,
        };
        start.Environment["PYTHONUTF8"] = "1";
        start.Environment["PYTHONIOENCODING"] = "utf-8";
        foreach (var argument in arguments)
        {
            start.ArgumentList.Add(argument);
        }
        using var process = new Process { StartInfo = start };
        try
        {
            process.Start();
        }
        catch (Exception exception)
        {
            return new ProcessResult(-1, "", exception.Message);
        }
        var stdout = process.StandardOutput.ReadToEndAsync();
        var stderr = process.StandardError.ReadToEndAsync();
        using var cancellation = new CancellationTokenSource(
            timeout ?? TimeSpan.FromMinutes(10)
        );
        try
        {
            await process.WaitForExitAsync(cancellation.Token);
        }
        catch (OperationCanceledException)
        {
            try
            {
                process.Kill(entireProcessTree: true);
            }
            catch (InvalidOperationException)
            {
                // The process exited between cancellation and termination.
            }
            await process.WaitForExitAsync();
            return new ProcessResult(-1, await stdout, await stderr, true);
        }
        return new ProcessResult(process.ExitCode, await stdout, await stderr, false);
    }

    private sealed record ProcessResult(
        int ExitCode,
        string Stdout,
        string Stderr,
        bool TimedOut = false
    );
}
