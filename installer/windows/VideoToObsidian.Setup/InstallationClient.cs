using System.Diagnostics;
using System.IO;
using System.Reflection;

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

    public async Task EnsureInstalledAsync(Action<string> report)
    {
        if (File.Exists(CoreExecutable))
        {
            report("视知库核心已安装，正在检查应用。");
        }
        else
        {
            var python = await EnsurePythonAsync(report);
            report("正在创建独立运行环境…");
            Directory.CreateDirectory(_appRoot);
            await RunCheckedAsync(
                python,
                new[] { "-m", "venv", Path.Combine(_appRoot, "runtime") }
            );
            var wheel = ExtractEmbeddedWheel();
            report("正在安装视知库核心及下载组件…");
            await RunCheckedAsync(
                Path.Combine(_appRoot, "runtime", "Scripts", "python.exe"),
                new[]
                {
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "--upgrade",
                    wheel,
                }
            );
            if (!File.Exists(CoreExecutable))
            {
                throw new InvalidOperationException("核心组件安装后未找到可执行文件。");
            }
        }

        await EnsureWingetPackageAsync("Mozilla.Firefox", "Firefox", report);
        await EnsureWingetPackageAsync("Obsidian.Obsidian", "Obsidian", report);
        await EnsureWingetPackageAsync("Gyan.FFmpeg", "ffmpeg", report);
        await EnsureFirefoxProfileAsync(report);
    }

    private async Task<string> EnsurePythonAsync(Action<string> report)
    {
        var discovered = await DiscoverPythonAsync();
        if (discovered is not null)
        {
            return discovered;
        }
        report("未发现 Python，正通过 Windows 官方软件源安装…");
        await RunCheckedAsync(
            "winget",
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
                new[] { version, "-c", "import sys; print(sys.executable)" }
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

    private static async Task EnsureWingetPackageAsync(
        string id,
        string displayName,
        Action<string> report
    )
    {
        report($"正在检查 {displayName}…");
        var list = await TryCaptureAsync("winget", new[] { "list", "--id", id, "--exact" });
        if (list.ExitCode == 0 && list.Stdout.Contains(id, StringComparison.OrdinalIgnoreCase))
        {
            return;
        }
        report($"正在安装 {displayName}…");
        await RunCheckedAsync(
            "winget",
            new[]
            {
                "install",
                "--id",
                id,
                "--exact",
                "--silent",
                "--accept-package-agreements",
                "--accept-source-agreements",
            }
        );
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
        var firefox = candidates.FirstOrDefault(File.Exists);
        if (firefox is null)
        {
            throw new InvalidOperationException("Firefox 已安装但未找到可执行文件。");
        }
        report("正在创建视知库专用登录空间…");
        await RunCheckedAsync(firefox, new[] { "-CreateProfile", "VideoToObsidian" });
    }

    private static async Task RunCheckedAsync(string executable, IEnumerable<string> arguments)
    {
        var result = await TryCaptureAsync(executable, arguments);
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
        IEnumerable<string> arguments
    )
    {
        var start = new ProcessStartInfo
        {
            FileName = executable,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
        };
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
        await process.WaitForExitAsync();
        return new ProcessResult(process.ExitCode, await stdout, await stderr);
    }

    private sealed record ProcessResult(int ExitCode, string Stdout, string Stderr);
}
