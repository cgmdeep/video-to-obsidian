"""OS keychain access with an explicit environment fallback."""

from __future__ import annotations

import os

import keyring
from keyring.errors import KeyringError


SERVICE_NAME = "video-to-obsidian"
KIMI_ACCOUNT = "KIMI_API_KEY"


class SecretError(RuntimeError):
    pass


def get_kimi_api_key() -> str:
    environment = os.environ.get("KIMI_API_KEY", "").strip()
    if environment:
        return environment
    try:
        return (keyring.get_password(SERVICE_NAME, KIMI_ACCOUNT) or "").strip()
    except KeyringError:
        return ""


def kimi_key_source() -> str:
    if os.environ.get("KIMI_API_KEY", "").strip():
        return "environment"
    try:
        if (keyring.get_password(SERVICE_NAME, KIMI_ACCOUNT) or "").strip():
            return "keyring"
    except KeyringError:
        return "unavailable"
    return "missing"


def set_kimi_api_key(value: str) -> None:
    secret = (value or "").strip()
    if len(secret) < 10 or any(character.isspace() for character in secret):
        raise SecretError("Kimi API Key 格式无效。")
    try:
        keyring.set_password(SERVICE_NAME, KIMI_ACCOUNT, secret)
    except KeyringError as exc:
        raise SecretError("系统钥匙串不可用；请改用仅注入当前服务进程的环境变量。") from exc


def delete_kimi_api_key() -> bool:
    try:
        existing = keyring.get_password(SERVICE_NAME, KIMI_ACCOUNT)
        if not existing:
            return False
        keyring.delete_password(SERVICE_NAME, KIMI_ACCOUNT)
        return True
    except KeyringError as exc:
        raise SecretError("无法从系统钥匙串删除 Kimi API Key。") from exc

