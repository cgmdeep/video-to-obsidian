using System.Diagnostics;
using System.IO;
using System.Text.Json;
using System.Windows;

namespace VideoToObsidian.Setup;

public partial class MainWindow : Window
{
    private readonly BackendClient _backend = new();
    private readonly string _workspacePath;

    public MainWindow()
    {
        InitializeComponent();
        var documents = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);
        _workspacePath = Path.Combine(documents, "视知库助手");
        VaultPathBox.Text = Path.Combine(documents, "视知库");
        Loaded += async (_, _) => await RefreshStatusAsync();
    }

    private async void PrepareButton_Click(object sender, RoutedEventArgs e)
    {
        await GuardedAsync(async () =>
        {
            await _backend.RunAsync(
                new[] { "init", "--vault", VaultPathBox.Text, "--reuse-existing" }
            );
            await _backend.RunJsonAsync(
                new[] { "bootstrap-workspace", "--workspace", _workspacePath, "--json" }
            );
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
            KimiKeyBox.Clear();
            await RefreshStatusAsync();
        });
    }

    private async void ConfigureMoonshotButton_Click(object sender, RoutedEventArgs e)
    {
        await GuardedAsync(async () =>
        {
            await _backend.RunJsonAsync(new[] { "configure-zcode-moonshot", "--json" });
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

    private void OpenWorkspaceButton_Click(object sender, RoutedEventArgs e)
    {
        Directory.CreateDirectory(_workspacePath);
        Process.Start(new ProcessStartInfo(_workspacePath) { UseShellExecute = true });
    }

    private async void RefreshButton_Click(object sender, RoutedEventArgs e)
    {
        await RefreshStatusAsync();
    }

    private async Task RefreshStatusAsync()
    {
        await GuardedAsync(async () =>
        {
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
