import io
import json
from types import SimpleNamespace

import video_to_obsidian.cli as cli


def test_installer_can_set_key_over_stdin_without_echo(monkeypatch, capsys) -> None:
    captured = {}
    monkeypatch.setattr(cli.sys, "stdin", io.StringIO("secret-value-123\n"))
    monkeypatch.setattr(
        cli,
        "set_kimi_api_key",
        lambda value: captured.update(value=value),
    )

    assert cli.main(["set-kimi-key", "--stdin", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert captured["value"] == "secret-value-123"
    assert payload == {
        "ok": True,
        "secret_displayed": False,
        "paid_call_performed": False,
    }
    assert "secret-value-123" not in json.dumps(payload)


def test_installer_rejects_empty_stdin_key(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli.sys, "stdin", io.StringIO(""))
    assert cli.main(["set-kimi-key", "--stdin", "--json"]) == 2
    assert "没有 Kimi API Key" in capsys.readouterr().out


def test_installer_can_switch_profile_without_paid_call(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "update_profile",
        lambda profile, config_path=None: (config_path, True),
    )
    assert cli.main(
        ["set-profile", "--profile", "transcript", "--config", "config.toml", "--json"]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["changed"] is True
    assert payload["profile"] == "transcript"
    assert payload["transcript_mode"] == "local"
    assert payload["contains_secrets"] is False
    assert payload["paid_call_performed"] is False


def test_ensure_zcode_model_reports_missing_key_without_error(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "get_kimi_api_key", lambda: None)
    assert cli.main(["ensure-zcode-model", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["changed"] is False
    assert payload["reason"] == "kimi_key_missing"
    assert payload["secret_displayed"] is False
    assert payload["paid_call_performed"] is False


def test_installer_can_harden_zcode_permissions_without_paid_call(
    monkeypatch, capsys
) -> None:
    monkeypatch.setattr(
        cli,
        "harden_zcode_model_permissions",
        lambda path: {
            "ok": True,
            "changed": True,
            "reason": "permissions_private",
            "permissions_private": True,
            "secret_displayed": False,
            "paid_call_performed": False,
        },
    )

    assert cli.main(["harden-zcode-model-permissions", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["permissions_private"] is True
    assert payload["secret_displayed"] is False
    assert payload["paid_call_performed"] is False


def test_audit_vault_cli_is_free_and_uses_configured_vault(monkeypatch, capsys) -> None:
    configured = SimpleNamespace(vault_path="C:/Vault")
    monkeypatch.setattr(cli, "load_settings", lambda _: configured)
    monkeypatch.setattr(
        cli,
        "audit_vault",
        lambda vault: {
            "ok": True,
            "paid_call_performed": False,
            "vault": str(vault),
            "markdown_files": 3,
            "managed_notes": 2,
            "managed_identities": 2,
            "duplicate_groups": [],
            "unreadable_files": 0,
        },
    )
    assert cli.main(["audit-vault", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["paid_call_performed"] is False
    assert payload["duplicate_groups"] == []


def test_support_report_cli_is_bounded_and_free(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "doctor_payload",
        lambda _: {
            "ok": True,
            "paid_call_performed": False,
            "checks": [
                {
                    "name": "config",
                    "ok": True,
                    "required": True,
                    "detail": r"C:\\Users\\private-user\\config.toml",
                }
            ],
        },
    )
    monkeypatch.setattr(
        cli,
        "inspect_workspace",
        lambda _: {
            "ok": True,
            "exists": True,
            "managed_marker": True,
            "managed_rules": True,
            "workspace_mcp": True,
            "workspace": r"C:\\Users\\private-user\\Documents\\视知库助手",
        },
    )
    monkeypatch.setattr(
        cli,
        "inspect_zcode_models",
        lambda _: {
            "ok": True,
            "config_exists": True,
            "config": r"C:\\Users\\private-user\\.zcode\\v2\\config.json",
            "providers": [{"name": "private-provider", "secret_present": True}],
            "usable_provider_count": 1,
            "has_moonshot_provider": True,
            "has_coding_plan_provider": False,
            "permissions_private": None,
        },
    )

    assert cli.main(["support-report", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    serialized = json.dumps(payload)
    assert payload["ok"] is True
    assert payload["contains_secrets"] is False
    assert payload["contains_local_paths"] is False
    assert payload["paid_call_performed"] is False
    assert "private-user" not in serialized
    assert "private-provider" not in serialized
