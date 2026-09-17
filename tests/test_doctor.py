from pathlib import Path

from video_to_obsidian.config import initialize_settings
from video_to_obsidian.doctor import _firefox_profile_exists, doctor_payload


def test_doctor_never_performs_paid_call(tmp_path: Path, monkeypatch) -> None:
    config = initialize_settings(
        tmp_path / "vault",
        config_path=tmp_path / "config.toml",
        runtime_root=tmp_path / "private",
    )
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    payload = doctor_payload(config)
    assert payload["paid_call_performed"] is False
    checks = {item["name"]: item for item in payload["checks"]}
    assert checks["config"]["ok"] is True
    assert checks["vault"]["ok"] is True
    assert checks["kimi_key"]["ok"] is False


def test_firefox_profile_is_matched_by_name(tmp_path: Path) -> None:
    profiles = tmp_path / "profiles.ini"
    profiles.write_text(
        "[Profile0]\nName=default-release\nPath=Profiles/default\n\n"
        "[Profile1]\nName=VideoToObsidian\nPath=Profiles/video\n",
        encoding="utf-8",
    )
    assert _firefox_profile_exists("VideoToObsidian", profiles_file=profiles) is True
    assert _firefox_profile_exists("missing", profiles_file=profiles) is False
