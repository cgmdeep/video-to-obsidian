from __future__ import annotations

import re
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

from video_to_obsidian import __version__


ROOT = Path(__file__).resolve().parents[1]


def test_release_versions_are_aligned() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    python_version = project["project"]["version"]
    assert python_version == __version__

    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)a(\d+)", python_version)
    assert match is not None
    major, minor, patch, alpha = match.groups()
    informational_version = f"{major}.{minor}.{patch}-alpha.{alpha}"
    file_version = f"{major}.{minor}.{patch}.{alpha}"

    csproj = ET.parse(
        ROOT
        / "installer"
        / "windows"
        / "VideoToObsidian.Setup"
        / "VideoToObsidian.Setup.csproj"
    ).getroot()
    values = {child.tag: child.text for group in csproj.findall("PropertyGroup") for child in group}
    assert values["Version"] == informational_version
    assert values["FileVersion"] == file_version
    assert values["InformationalVersion"] == informational_version
    assert (ROOT / "docs" / "releases" / f"v{informational_version}.md").is_file()


def test_obsidian_plugin_uses_utf8_json_and_narrow_safe_layout() -> None:
    source = (ROOT / "obsidian-plugin" / "main.ts").read_text(encoding="utf-8")
    styles = (ROOT / "obsidian-plugin" / "styles.css").read_text(encoding="utf-8")

    assert 'PYTHONUTF8: "1"' in source
    assert 'PYTHONIOENCODING: "utf-8"' in source
    assert "overflow-x:hidden" in styles
    assert "text-overflow:ellipsis" in styles
    assert "white-space:pre-line" in styles
    assert "overflow-wrap:anywhere" in styles
