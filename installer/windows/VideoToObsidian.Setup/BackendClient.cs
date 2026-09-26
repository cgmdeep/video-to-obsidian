using System.Diagnostics;
using System.IO;
using System.Text.Json;

namespace VideoToObsidian.Setup;

internal sealed class BackendClient
{
    private readonly string _executable;

    public BackendClient()
    {
        var configured = Environment.GetEnvironmentVariable("VTO_CLI_PATH");
        var bundled = Path.Combine(
            AppContext.BaseDirectory,
            "runtime",
            "Scripts",
            "video-to-obsidian.exe"
        );
        _executable = !string.IsNullOrWhiteSpace(configured)
            ? configured
            : File.Exists(bundled) ? bundled : "video-to-obsidian";
    }

    public async Task<JsonDocument> RunJsonAsync(
        IEnumerable<string> arguments,
        string? secretStandardInput = null
    )
    {
        var output = await RunAsync(arguments, secretStandardInput);
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
        string? secretStandardInput = null
    )
    {
        var start = new ProcessStartInfo
        {
            FileName = _executable,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            RedirectStandardInput = secretStandardInput is not null,
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
        await process.WaitForExitAsync();
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
