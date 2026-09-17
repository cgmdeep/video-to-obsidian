import video_to_obsidian.secrets as secrets


def test_environment_key_has_priority(monkeypatch) -> None:
    monkeypatch.setenv("KIMI_API_KEY", "environment-secret")
    monkeypatch.setattr(secrets.keyring, "get_password", lambda service, account: "keyring-secret")
    assert secrets.get_kimi_api_key() == "environment-secret"
    assert secrets.kimi_key_source() == "environment"


def test_keyring_is_used_without_environment(monkeypatch) -> None:
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    monkeypatch.setattr(secrets.keyring, "get_password", lambda service, account: "keyring-secret")
    assert secrets.get_kimi_api_key() == "keyring-secret"
    assert secrets.kimi_key_source() == "keyring"


def test_set_key_never_returns_or_prints_value(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(
        secrets.keyring,
        "set_password",
        lambda service, account, value: captured.update(
            {"service": service, "account": account, "value": value}
        ),
    )
    assert secrets.set_kimi_api_key("secret-value-123") is None
    assert captured["service"] == secrets.SERVICE_NAME
    assert captured["account"] == secrets.KIMI_ACCOUNT
    assert captured["value"] == "secret-value-123"

