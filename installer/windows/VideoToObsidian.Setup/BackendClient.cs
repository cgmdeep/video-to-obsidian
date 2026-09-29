using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.Json;

namespace VideoToObsidian.Setup;

internal sealed class BackendClient
{
    private static readonly TimeSpan DefaultTimeout = TimeSpan.FromMinutes(5);
    private readonly string? _configuredExecutable;

    public BackendClient()
    {
        _configuredExecutable = Environment.GetEnvironmentVariable("VTO_CLI_PATH");
    }

    private string ResolveExecutable()
    {
        var installed = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "VideoToObsidian",
            "runtime",
            "Scripts",
            "video-to-obsidian.exe"
        );
        var besideSetup = Path.Combine(
            AppContext.BaseDirectory,
            "runtime",
            "Scripts",
            "video-to-obsidian.exe"
        );
        if (!string.IsNullOrWhiteSpace(_configuredExecutable))
        {
            return _configuredExecutable;
        }
        if (File.Exists(installed))
        {
            return installed;
        }
        return File.Exists(besideSetup) ? besideSetup : "video-to-obsidian";
    }

    public async Task<JsonDocument> RunJsonAsync(
        IEnumerable<string> arguments,
        string? secretStandardInput = null,
        TimeSpan? timeout = null
    )
    {
        var output = await RunAsync(arguments, secretStandardInput, timeout);
        try
        {
            return JsonDocument.Parse(output);
        }
        catch (JsonException exception)
        {
            throw new InvalidOperationException("后端未返回有效状态。", exception);
        }
    }

    public async Task<string> RunAsync(
        IEnumerable<string> arguments,
        string? secretStandardInput = null,
        TimeSpan? timeout = null
    )
    {
        var start = new ProcessStartInfo
        {
            FileName = ResolveExecutable(),
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            RedirectStandardInput = secretStandardInput is not null,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
            CreateNoWindow = true,
        };
        foreach (var argument in arguments)
        {
            start.ArgumentList.Add(argument);
        }
        var machinePath = Environment.GetEnvironmentVariable(
            "Path",
            EnvironmentVariableTarget.Machine
        );
        var userPath = Environment.GetEnvironmentVariable(
            "Path",
            EnvironmentVariableTarget.User
        );
        start.Environment["PATH"] = string.Join(
            ";",
            new[] { machinePath, userPath }.Where(value => !string.IsNullOrWhiteSpace(value))
        );
        start.Environment["PYTHONUTF8"] = "1";
        start.Environment["PYTHONIOENCODING"] = "utf-8";
        using var process = new Process { StartInfo = start };
        try
        {
            process.Start();
        }
        catch (Exception exception)
        {
            throw new InvalidOperationException(
                "未找到视知库核心组件，请先完成安装。",
                exception
            );
        }
        if (secretStandardInput is not null)
        {
            await process.StandardInput.WriteLineAsync(secretStandardInput);
            process.StandardInput.Close();
        }
        var stdoutTask = process.StandardOutput.ReadToEndAsync();
        var stderrTask = process.StandardError.ReadToEndAsync();
        using var timeoutSource = new CancellationTokenSource(timeout ?? DefaultTimeout);
        try
        {
            await process.WaitForExitAsync(timeoutSource.Token);
        }
        catch (OperationCanceledException) when (timeoutSource.IsCancellationRequested)
        {
            try
            {
                process.Kill(entireProcessTree: true);
                await process.WaitForExitAsync();
            }
            catch (InvalidOperationException)
            {
                // The process exited between timeout detection and cleanup.
            }
            throw new TimeoutException(
                "本机操作等待超过 5 分钟，已停止相关进程。请点击“重新检查”；若仍失败再导出脱敏诊断报告。"
            );
        }
        var stdout = await stdoutTask;
        var stderr = await stderrTask;
        if (process.ExitCode != 0)
        {
            var detail = string.IsNullOrWhiteSpace(stdout) ? stderr : stdout;
            throw new InvalidOperationException(
                string.IsNullOrWhiteSpace(detail) ? "操作未完成。" : detail.Trim()
            );
        }
        return stdout;
    }
}
