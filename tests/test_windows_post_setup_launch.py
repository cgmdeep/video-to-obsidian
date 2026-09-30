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

    assert "OpenPreparedDestinations();" in prepare_handler
    assert "OpenPreparedDestinations();" in key_handler


def test_post_setup_launch_uses_registered_vault_and_workspace_argument() -> None:
    source = MAIN_WINDOW.read_text(encoding="utf-8")
    helper = source.split("private void OpenPreparedDestinations()", 1)[1].split(
        "private static string? FindZCodeExecutable", 1
    )[0]

    assert "ObsidianVaultRegistry.EnsureRegistered(vaultPath)" in helper
    assert '"obsidian://open?vault="' in helper
    assert 'Arguments = $"\\"{_workspacePath}\\""' in helper
    assert "尚未找到 ZCode" in helper
