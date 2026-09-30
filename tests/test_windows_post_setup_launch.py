from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN_WINDOW = (
    ROOT
    / "installer"
    / "windows"
    / "VideoToObsidian.Setup"
    / "MainWindow.xaml.cs"
)


def test_successful_prepare_and_key_save_open_managed_destinations() -> None:
    source = MAIN_WINDOW.read_text(encoding="utf-8")

    prepare_handler = source.split(
        "private async void PrepareButton_Click", 1
    )[1].split("private async void SaveKeyButton_Click", 1)[0]
    key_handler = source.split(
        "private async void SaveKeyButton_Click", 1
    )[1].split("private void OpenBotGuideButton_Click", 1)[0]

    assert "await OpenPreparedDestinationsAsync();" in prepare_handler
    assert "await OpenPreparedDestinationsAsync();" in key_handler


def test_post_setup_launch_uses_registered_vault_and_workspace_argument() -> None:
    source = MAIN_WINDOW.read_text(encoding="utf-8")
    helper = source.split("private async Task OpenPreparedDestinationsAsync()", 1)[1].split(
        "private static string? FindZCodeExecutable", 1
    )[0]

    assert "await RestartAndOpenObsidianVaultAsync(vaultPath)" in helper
    assert 'Process.GetProcessesByName("Obsidian")' in helper
    assert "process.CloseMainWindow();" in helper
    assert "process.Kill(entireProcessTree: true);" in helper
    assert "ObsidianVaultRegistry.EnsureRegistered(vaultPath)" in helper
    assert '"obsidian://open?vault="' in helper
    assert 'Arguments = $"--open-workspace \\"{workspacePath}\\""' in helper
    assert "尚未找到 ZCode" in helper
