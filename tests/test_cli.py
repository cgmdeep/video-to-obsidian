import io
import json

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


def test_ensure_zcode_model_reports_missing_key_without_error(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "get_kimi_api_key", lambda: None)
    assert cli.main(["ensure-zcode-model", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["changed"] is False
    assert payload["reason"] == "kimi_key_missing"
    assert payload["secret_displayed"] is False
    assert payload["paid_call_performed"] is False
