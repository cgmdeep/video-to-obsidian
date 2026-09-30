from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_windows_installer_does_not_depend_on_msstore_search() -> None:
    source = (
        ROOT
        / "installer/windows/VideoToObsidian.Setup/InstallationClient.cs"
    ).read_text(encoding="utf-8")

    assert '"msstore"' not in source
    assert 'new[] { "list", "--id", id, "--exact", "--source", "winget" }' in source
    assert '"Python.Python.3.12",\n                "--exact",\n                "--source",\n                "winget"' in source
    assert '"Obsidian.Obsidian",\n                "--exact",\n                "--source",\n                "winget"' in source


def test_windows_installer_reuses_working_ffmpeg() -> None:
    source = (
        ROOT
        / "installer/windows/VideoToObsidian.Setup/InstallationClient.cs"
    ).read_text(encoding="utf-8")

    assert "if (await HasWorkingFfmpegAsync())" in source
    assert 'new[] { "-version" }' in source


def test_advanced_install_script_pins_winget_source() -> None:
    source = (ROOT / "scripts/install.ps1").read_text(encoding="utf-8")

    assert "winget install --id $Id --exact --source winget" in source
