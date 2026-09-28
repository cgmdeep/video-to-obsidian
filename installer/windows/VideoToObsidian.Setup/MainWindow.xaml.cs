using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text;
using System.Text.Json;
using System.Windows;

namespace VideoToObsidian.Setup;

public partial class MainWindow : Window
{
    private readonly BackendClient _backend = new();
    private readonly MachinePreparationClient _preparation = new();
    private readonly string _workspacePath;

    public MainWindow()
    {
        InitializeComponent();
        _workspacePath = MachinePreparationClient.DefaultWorkspacePath;
        VaultPathBox.Text = MachinePreparationClient.DefaultVaultPath;
        Loaded += async (_, _) => await RefreshStatusAsync();
    }

    private async void PrepareButton_Click(object sender, RoutedEventArgs e)
    {
        await GuardedAsync(async () =>
        {
            await _preparation.PrepareAsync(
                VaultPathBox.Text,
                _workspacePath,
                message =>
            {
                Dispatcher.Invoke(() => StatusText.Text = message);
            });
            await RefreshStatusAsync();
        });
    }

    private async void SaveKeyButton_Click(object sender, RoutedEventArgs e)
    {
        var secret = KimiKeyBox.Password;
        if (string.IsNullOrWhiteSpace(secret))
        {
            MessageBox.Show("请输入 Kimi API Key。", "视知库");
            return;
        }
        await GuardedAsync(async () =>
        {
            await _backend.RunJsonAsync(
                new[] { "set-kimi-key", "--stdin", "--json" },
                secret
            );
            await _backend.RunJsonAsync(new[] { "ensure-zcode-model", "--json" });
            KimiKeyBox.Clear();
            await RefreshStatusAsync();
        });
    }

    private void OpenBotGuideButton_Click(object sender, RoutedEventArgs e)
    {
        Process.Start(
            new ProcessStartInfo("https://zcode.z.ai/cn/docs/bot-channel")
            {
                UseShellExecute = true,
            }
        );
    }

    private void OpenDouyinLoginButton_Click(object sender, RoutedEventArgs e)
    {
        OpenFirefoxProfile("https://www.douyin.com/");
    }

    private void OpenBilibiliLoginButton_Click(object sender, RoutedEventArgs e)
    {
        OpenFirefoxProfile("https://www.bilibili.com/");
    }

    private static void OpenFirefoxProfile(string url)
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
        var firefox = candidates.FirstOrDefault(File.Exists);
        if (firefox is null)
        {
            MessageBox.Show("请先点击“一键准备本机”，安装并创建专用 Firefox 登录空间。", "视知库");
            return;
        }
        Process.Start(
            new ProcessStartInfo(firefox)
            {
                UseShellExecute = true,
                Arguments = $"-P VideoToObsidian -no-remote \"{url}\"",
            }
        );
    }

    private void OpenZCodeInstallButton_Click(object sender, RoutedEventArgs e)
    {
        Process.Start(
            new ProcessStartInfo("https://zcode.z.ai/cn/docs/install")
            {
                UseShellExecute = true,
            }
        );
    }

    private void OpenWorkspaceButton_Click(object sender, RoutedEventArgs e)
    {
        Directory.CreateDirectory(_workspacePath);
        Process.Start(new ProcessStartInfo(_workspacePath) { UseShellExecute = true });
    }

    private void CopyWorkspacePathButton_Click(object sender, RoutedEventArgs e)
    {
        Directory.CreateDirectory(_workspacePath);
        Clipboard.SetText(_workspacePath);
        MessageBox.Show("工作区路径已复制。请在 ZCode 的“打开工作区”中选择该目录。", "视知库");
    }

    private void OpenVaultButton_Click(object sender, RoutedEventArgs e)
    {
        var vaultPath = VaultPathBox.Text.Trim();
        if (string.IsNullOrWhiteSpace(vaultPath) || !Directory.Exists(vaultPath))
        {
            MessageBox.Show("请先点击“一键准备本机”创建知识库。", "视知库");
            return;
        }
        var uri = "obsidian://open?path=" + Uri.EscapeDataString(vaultPath);
        Process.Start(new ProcessStartInfo(uri) { UseShellExecute = true });
    }

    private async void RefreshButton_Click(object sender, RoutedEventArgs e)
    {
        await RefreshStatusAsync();
    }

    private async void ExportDiagnosticsButton_Click(object sender, RoutedEventArgs e)
    {
        await GuardedAsync(async () =>
        {
            using var status = await _backend.RunJsonAsync(
                new[] { "onboarding-status", "--workspace", _workspacePath, "--json" }
            );
            var report = new Dictionary<string, object?>
            {
                ["schema_version"] = 1,
                ["generated_at_utc"] = DateTimeOffset.UtcNow,
                ["installer_version"] = typeof(MainWindow).Assembly
                    .GetCustomAttribute<AssemblyInformationalVersionAttribute>()
                    ?.InformationalVersion
                    ?? typeof(MainWindow).Assembly.GetName().Version?.ToString(),
                ["contains_secrets"] = false,
                ["paid_call_performed"] = false,
                ["onboarding_status"] = status.RootElement.Clone(),
            };
            var desktop = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
            var path = Path.Combine(desktop, "视知库诊断报告.json");
            var json = JsonSerializer.Serialize(
                report,
                new JsonSerializerOptions { WriteIndented = true }
            );
            await File.WriteAllTextAsync(path, json, new UTF8Encoding(false));
            Process.Start(new ProcessStartInfo("explorer.exe", $"/select,\"{path}\"")
            {
                UseShellExecute = true,
            });
            MessageBox.Show(
                "脱敏诊断报告已保存到桌面。报告不包含 API Key、Cookie，也不会调用付费模型。",
                "视知库"
            );
        }, showSuccess: false);
    }

    private async Task RefreshStatusAsync()
    {
        if (!_preparation.IsInstalled)
        {
            StatusText.Text = "尚未安装视知库核心。请先点击“一键准备本机”。";
            return;
        }
        await GuardedAsync(async () =>
        {
            await _backend.RunJsonAsync(new[] { "ensure-zcode-model", "--json" });
            using var document = await _backend.RunJsonAsync(
                new[] { "onboarding-status", "--workspace", _workspacePath, "--json" }
            );
            var root = document.RootElement;
            var ready = root.GetProperty("ready_for_free_bot_test").GetBoolean();
            var actions = root.GetProperty("next_actions")
                .EnumerateArray()
                .Select(item => item.GetString())
                .Where(item => !string.IsNullOrWhiteSpace(item));
            StatusText.Text = ready
                ? "本机已就绪。下一步：在 ZCode 专用工作区连接微信，发送‘检查系统’。"
                : "尚需完成：" + string.Join("、", actions);
        }, showSuccess: false);
    }

    private async Task GuardedAsync(Func<Task> action, bool showSuccess = true)
    {
        try
        {
            IsEnabled = false;
            await action();
            if (showSuccess)
            {
                MessageBox.Show("操作完成。", "视知库");
            }
        }
        catch (Exception exception)
        {
            StatusText.Text = exception.Message;
            MessageBox.Show(exception.Message, "视知库", MessageBoxButton.OK, MessageBoxImage.Warning);
        }
        finally
        {
            IsEnabled = true;
        }
    }
}
