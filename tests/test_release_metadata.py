from __future__ import annotations

import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

from video_to_obsidian import __version__


ROOT = Path(__file__).resolve().parents[1]


def test_release_versions_are_aligned() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["version"] == __version__ == "0.1.0a3"

    csproj = ET.parse(
        ROOT
        / "installer"
        / "windows"
        / "VideoToObsidian.Setup"
        / "VideoToObsidian.Setup.csproj"
    ).getroot()
    values = {child.tag: child.text for group in csproj.findall("PropertyGroup") for child in group}
    assert values["Version"] == "0.1.0-alpha.3"
    assert values["FileVersion"] == "0.1.0.3"
    assert values["InformationalVersion"] == "0.1.0-alpha.3"
