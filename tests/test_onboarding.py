import json
import os
import stat
from pathlib import Path

import pytest

from video_to_obsidian.onboarding import (
    MANAGED_HEADER,
    MOONSHOT_PROVIDER_ID,
    OnboardingError,
    bootstrap_workspace,
    build_support_report,
    build_moonshot_model_config,
    configure_zcode_moonshot,
    ensure_zcode_model,
    harden_zcode_model_permissions,
    inspect_zcode_models,
    inspect_workspace,
    onboarding_status,
)


def test_bootstrap_workspace_creates_managed_rules_and_workspace_mcp(tmp_path: Path) -> None:
    target = tmp_path / "视知库助手"
    payload = bootstrap_workspace(target, command="python.exe")

    assert payload["paid_call_performed"] is False
    rules = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert rules.startswith(MANAGED_HEADER)
    assert "video_analysis_usage" in rules
    assert "zcode_routing_usage.available=false" in rules
    assert "禁止猜测、混算" in rules
    config = json.loads((target / ".zcode/config.json").read_text(encoding="utf-8"))
    entry = config["mcp"]["servers"]["video-to-obsidian"]
    assert entry["command"] == "python.exe"
    assert entry["timeoutMs"] == 3_600_000
    assert "env" not in entry


def test_bootstrap_workspace_is_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "workspace"
    first = bootstrap_workspace(target, command="python.exe")
    second = bootstrap_workspace(target, command="python.exe")
    assert first == second
    assert inspect_workspace(target)["ok"] is True


def test_bootstrap_workspace_repair_upgrades_managed_timeout(tmp_path: Path) -> None:
    target = tmp_path / "workspace"
    bootstrap_workspace(target, command="python.exe", timeout_ms=1_200_000)

    bootstrap_workspace(target, command="python.exe")

    config = json.loads((target / ".zcode/config.json").read_text(encoding="utf-8"))
    assert config["mcp"]["servers"]["video-to-obsidian"]["timeoutMs"] == 3_600_000


def test_bootstrap_workspace_refuses_unmanaged_nonempty_directory(tmp_path: Path) -> None:
    target = tmp_path / "existing"
    target.mkdir()
    (target / "important.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(OnboardingError):
        bootstrap_workspace(target, command="python.exe")
    assert (target / "important.txt").read_text(encoding="utf-8") == "keep"


def test_model_status_never_returns_api_key_or_base_url(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "provider": {
                    "custom-moonshot": {
                        "name": "Moonshot",
                        "kind": "anthropic-compatible",
                        "source": "custom",
                        "options": {
                            "apiKey": "super-secret",
                            "baseURL": "https://api.moonshot.cn/anthropic",
                        },
                        "models": {"kimi-k2.7-code": {}},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    payload = inspect_zcode_models(path)
    serialized = json.dumps(payload)
    assert payload["ok"] is True
    assert payload["has_moonshot_provider"] is True
    assert payload["has_coding_plan_provider"] is False
    assert "super-secret" not in serialized
    assert "api.moonshot.cn" not in serialized
    assert payload["providers"][0]["secret_present"] is True


def test_model_status_accepts_non_plan_custom_provider(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "provider": {
                    "custom": {
                        "name": "Private Provider",
                        "kind": "openai-compatible",
                        "options": {"apiKey": "configured", "baseURL": "https://example.invalid"},
                        "models": {"small-router": {}},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    payload = inspect_zcode_models(path)
    assert payload["ok"] is True
    assert payload["usable_provider_count"] == 1
    assert payload["has_coding_plan_provider"] is False


def test_model_status_reports_missing_config_without_error(tmp_path: Path) -> None:
    payload = inspect_zcode_models(tmp_path / "missing.json")
    assert payload["ok"] is False
    assert payload["config_exists"] is False
    assert payload["paid_call_performed"] is False


def test_build_moonshot_config_preserves_other_providers() -> None:
    original = {"provider": {"existing": {"name": "Existing", "models": {"m": {}}}}}
    updated = build_moonshot_model_config(original, api_key="secret-value-123")
    assert updated["provider"]["existing"] == original["provider"]["existing"]
    moonshot = updated["provider"][MOONSHOT_PROVIDER_ID]
    assert moonshot["kind"] == "anthropic-compatible"
    assert moonshot["options"]["apiKey"] == "secret-value-123"
    assert "kimi-k2.7-code" in moonshot["models"]
    assert MOONSHOT_PROVIDER_ID not in original["provider"]


def test_build_moonshot_config_refuses_secret_overwrite() -> None:
    existing = build_moonshot_model_config({}, api_key="secret-value-123")
    with pytest.raises(OnboardingError):
        build_moonshot_model_config(existing, api_key="different-secret-456")


def test_configure_moonshot_creates_private_backup_and_never_returns_secret(
    tmp_path: Path,
) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"provider": {}}), encoding="utf-8")
    os.chmod(path, 0o644)
    payload = configure_zcode_moonshot(path, api_key="secret-value-123")
    serialized = json.dumps(payload)
    backup = Path(payload["backup"])
    assert backup.is_file()
    assert "secret-value-123" not in serialized
    assert payload["secret_displayed"] is False
    assert payload["paid_call_performed"] is False
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert stat.S_IMODE(backup.stat().st_mode) == 0o600


def test_model_status_reports_private_permissions(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"provider": {}}), encoding="utf-8")
    os.chmod(path, 0o644)
    payload = inspect_zcode_models(path)
    if os.name != "nt":
        assert payload["permissions_private"] is False


def test_harden_model_permissions_does_not_return_secret(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"provider": {"private": {"options": {"apiKey": "secret-value-123"}}}}),
        encoding="utf-8",
    )
    os.chmod(path, 0o644)

    payload = harden_zcode_model_permissions(path)

    assert payload["ok"] is True
    assert payload["permissions_private"] is True
    assert payload["secret_displayed"] is False
    assert payload["paid_call_performed"] is False
    assert "secret-value-123" not in json.dumps(payload)
    assert json.loads(path.read_text(encoding="utf-8"))["provider"]["private"]["options"]["apiKey"] == "secret-value-123"


def test_harden_missing_model_config_is_safe_noop(tmp_path: Path) -> None:
    payload = harden_zcode_model_permissions(tmp_path / "missing.json")
    assert payload == {
        "ok": True,
        "changed": False,
        "reason": "zcode_not_initialized",
        "permissions_private": None,
        "secret_displayed": False,
        "paid_call_performed": False,
    }


def test_ensure_model_preserves_existing_provider(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    original = {
        "provider": {
            "existing": {
                "name": "Existing",
                "kind": "openai-compatible",
                "options": {"apiKey": "already-set"},
                "models": {"router": {}},
            }
        }
    }
    path.write_text(json.dumps(original), encoding="utf-8")
    result = ensure_zcode_model(path, api_key="secret-value-123")
    assert result["ok"] is True
    assert result["changed"] is False
    assert result["reason"] == "existing_provider_preserved"
    assert json.loads(path.read_text(encoding="utf-8")) == original


def test_ensure_model_adds_moonshot_only_when_no_provider(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"provider": {}}), encoding="utf-8")
    result = ensure_zcode_model(path, api_key="secret-value-123")
    assert result["ok"] is True
    assert result["changed"] is True
    assert result["reason"] == "moonshot_added"
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert MOONSHOT_PROVIDER_ID in stored["provider"]


def test_ensure_model_waits_for_zcode_initialization(tmp_path: Path) -> None:
    path = tmp_path / "missing.json"
    result = ensure_zcode_model(path, api_key="secret-value-123")
    assert result["ok"] is False
    assert result["changed"] is False
    assert result["reason"] == "zcode_not_initialized"
    assert not path.exists()


def test_onboarding_status_returns_stable_next_actions() -> None:
    payload = onboarding_status(
        doctor={
            "ok": False,
            "paid_call_performed": False,
            "checks": [
                {"name": "config", "required": True, "ok": True},
                {"name": "kimi_key", "required": True, "ok": False},
                {"name": "ffmpeg", "required": True, "ok": False},
            ],
        },
        workspace={"ok": False, "paid_call_performed": False},
        zcode_models={"ok": False, "paid_call_performed": False},
    )
    assert payload["schema_version"] == 1
    assert payload["ready_for_free_bot_test"] is False
    assert payload["paid_call_performed"] is False
    assert payload["next_actions"] == [
        "set_kimi_key",
        "install_or_repair_dependencies",
        "bootstrap_workspace",
        "configure_zcode_model",
        "verify_bot_channel",
    ]


def test_support_report_omits_paths_provider_names_and_details() -> None:
    status = {
        "ok": True,
        "ready_for_free_bot_test": True,
        "doctor": {
            "ok": True,
            "checks": [
                {
                    "name": "config",
                    "ok": True,
                    "required": True,
                    "detail": r"配置可读：C:\\Users\\private-user\\config.toml",
                }
            ],
        },
        "workspace": {
            "ok": True,
            "exists": True,
            "managed_marker": True,
            "managed_rules": True,
            "workspace_mcp": True,
            "workspace": r"C:\\Users\\private-user\\Documents\\视知库助手",
        },
        "zcode_models": {
            "ok": True,
            "config_exists": True,
            "config": r"C:\\Users\\private-user\\.zcode\\v2\\config.json",
            "providers": [
                {
                    "provider_id": "private-provider-name",
                    "name": "Private Provider",
                    "secret_present": True,
                }
            ],
            "usable_provider_count": 1,
            "has_moonshot_provider": True,
            "has_coding_plan_provider": False,
            "permissions_private": True,
        },
        "next_actions": ["verify_bot_channel"],
    }

    report = build_support_report(status)
    serialized = json.dumps(report)

    assert report["contains_secrets"] is False
    assert report["contains_local_paths"] is False
    assert report["paid_call_performed"] is False
    assert report["doctor"]["checks"] == [
        {"name": "config", "ok": True, "required": True}
    ]
    assert "private-user" not in serialized
    assert "private-provider-name" not in serialized
    assert "Private Provider" not in serialized
    assert "config.toml" not in serialized
