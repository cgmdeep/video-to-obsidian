"""Installer-facing ZCode workspace and model diagnostics.

The functions in this module are intentionally free of network calls and paid model calls.  A
graphical installer can use their JSON-friendly payloads without parsing human terminal output.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .zcode import build_updated_config


WORKSPACE_SCHEMA = 1
WORKSPACE_MARKER = ".video-to-obsidian-workspace.json"
MANAGED_HEADER = "<!-- managed-by: video-to-obsidian -->"
MOONSHOT_PROVIDER_ID = "video-to-obsidian-moonshot"
MOONSHOT_BASE_URL = "https://api.moonshot.cn/anthropic"
MOONSHOT_ROUTER_MODEL = "kimi-k2.7-code"


class OnboardingError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderStatus:
    provider_id: str
    name: str
    kind: str
    enabled: bool
    secret_present: bool
    model_ids: tuple[str, ...]
    is_moonshot: bool
    is_coding_plan: bool
    disabled_reason_present: bool

    @property
    def usable_candidate(self) -> bool:
        return (
            self.enabled
            and self.secret_present
            and bool(self.model_ids)
            and not self.disabled_reason_present
        )

    def public_payload(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "name": self.name,
            "kind": self.kind,
            "enabled": self.enabled,
            "secret_present": self.secret_present,
            "model_ids": list(self.model_ids),
            "is_moonshot": self.is_moonshot,
            "is_coding_plan": self.is_coding_plan,
            "disabled_reason_present": self.disabled_reason_present,
            "usable_candidate": self.usable_candidate,
        }


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temp_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temp_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def _workspace_agents() -> str:
    return f"""{MANAGED_HEADER}
# 视知库助手工作区

本工作区只用于把用户主动发送的抖音或哔哩哔哩单视频写入 Obsidian。
默认使用简体中文回复。

## 固定路由

- 消息含 `v.douyin.com` 或 `douyin.com/video/`：调用 `video-to-obsidian` MCP 的 `analyze_douyin`。
- 消息含 `b23.tv`、`bilibili.com/video/BV` 或独立 BV 号：调用 `analyze_bilibili`。
- 把用户的完整分享文本原样传入 `share_text`，不要要求用户手工提取链接。
- 默认 `mode=vision`。只有同一条消息含精确短语“使用K3深度分析”时才使用 `mode=deep`。
- 默认 `save_video=false`；只有用户明确要求保存或归档原视频时才改为 `true`。

## 付费与重试边界

- ZCode 模型只负责识别路由、调用 MCP 并转述工具结果；不自己观看、总结或二次改写视频。
- 每条逻辑任务最多一次完整 Kimi 视频调用。
- 工具返回 `retryable=false` 时立即停止；不换模型、不增加 token、不自动再调。
- 不用标题、网页搜索或模型猜测冒充视频分析。

## 结果回复

- 只有工具真实返回并验证 `saved_to` 时，才能说笔记已入库。
- 只有工具真实返回归档路径时，才能说原视频已保存。
- 如实列出降级、失败步骤、模型 usage 和费用估算；不替失败管线报成功。

## 禁止范围

- 不修改本工作区以外的文件、ZCode 配置或 Obsidian `.obsidian`。
- 不安装微信 Hook、注入器或非官方机器人。
- 不读取微信历史消息；只处理用户主动发到当前 Bot Channel 的内容。
"""


def _workspace_readme() -> str:
    return f"""{MANAGED_HEADER}
# 视知库助手

这是安装器为 ZCode 微信 Bot Channel 创建的专用工作区。

日常使用时，直接在微信里把抖音或 B站的完整分享文本发给 ZCode Bot。
默认不保存原视频，默认不生成本地逐字稿。

请不要把 API Key、Cookie 或验证码写进这个目录。
"""


def bootstrap_workspace(
    workspace: Path,
    *,
    command: str,
    args: list[str] | None = None,
    timeout_ms: int = 1_200_000,
) -> dict[str, Any]:
    root = workspace.expanduser().resolve()
    marker = root / WORKSPACE_MARKER
    if root.exists():
        contents = list(root.iterdir())
        if contents and not marker.is_file():
            raise OnboardingError(f"目标目录非空且不是受管视知库工作区：{root}")
    root.mkdir(parents=True, exist_ok=True)

    agents_path = root / "AGENTS.md"
    readme_path = root / "README.md"
    zcode_config = root / ".zcode" / "config.json"
    for path in (agents_path, readme_path):
        if path.exists() and not path.read_text(encoding="utf-8").startswith(MANAGED_HEADER):
            raise OnboardingError(f"拒绝覆盖非受管文件：{path}")

    existing_config: dict[str, Any] = {}
    if zcode_config.exists():
        try:
            existing_config = json.loads(zcode_config.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise OnboardingError(f"ZCode 工作区配置无法读取：{zcode_config}") from exc
        if not isinstance(existing_config, dict):
            raise OnboardingError("ZCode 工作区配置顶层必须是对象。")

    updated_config = build_updated_config(
        existing_config,
        command=command,
        args=args,
        timeout_ms=timeout_ms,
        replace_existing=False,
    )
    _atomic_text(agents_path, _workspace_agents())
    _atomic_text(readme_path, _workspace_readme())
    _atomic_json(zcode_config, updated_config)
    _atomic_json(
        marker,
        {
            "schema_version": WORKSPACE_SCHEMA,
            "managed_by": "video-to-obsidian",
            "managed_files": ["AGENTS.md", "README.md", ".zcode/config.json"],
        },
    )
    return {
        "ok": True,
        "workspace": str(root),
        "zcode_config": str(zcode_config),
        "paid_call_performed": False,
    }


def inspect_workspace(workspace: Path) -> dict[str, Any]:
    root = workspace.expanduser().resolve()
    marker = root / WORKSPACE_MARKER
    agents = root / "AGENTS.md"
    zcode_config = root / ".zcode" / "config.json"
    marker_ok = False
    if marker.is_file():
        try:
            marker_payload = json.loads(marker.read_text(encoding="utf-8"))
            marker_ok = (
                isinstance(marker_payload, dict)
                and marker_payload.get("schema_version") == WORKSPACE_SCHEMA
                and marker_payload.get("managed_by") == "video-to-obsidian"
            )
        except (OSError, json.JSONDecodeError):
            marker_ok = False
    agents_ok = False
    if agents.is_file():
        try:
            agents_ok = agents.read_text(encoding="utf-8").startswith(MANAGED_HEADER)
        except OSError:
            agents_ok = False
    mcp_ok = False
    if zcode_config.is_file():
        try:
            zcode_payload = json.loads(zcode_config.read_text(encoding="utf-8"))
            mcp_ok = isinstance(
                (((zcode_payload.get("mcp") or {}).get("servers") or {}).get(
                    "video-to-obsidian"
                )),
                dict,
            )
        except (AttributeError, OSError, json.JSONDecodeError):
            mcp_ok = False
    return {
        "ok": marker_ok and agents_ok and mcp_ok,
        "workspace": str(root),
        "exists": root.is_dir(),
        "managed_marker": marker_ok,
        "managed_rules": agents_ok,
        "workspace_mcp": mcp_ok,
        "paid_call_performed": False,
    }


def onboarding_status(
    *,
    doctor: dict[str, Any],
    workspace: dict[str, Any],
    zcode_models: dict[str, Any],
) -> dict[str, Any]:
    """Combine free diagnostics into the stable contract consumed by the future GUI."""

    next_actions: list[str] = []
    checks = doctor.get("checks") if isinstance(doctor.get("checks"), list) else []
    failed_names = {
        str(item.get("name"))
        for item in checks
        if isinstance(item, dict) and item.get("required") and not item.get("ok")
    }
    if "config" in failed_names or "vault" in failed_names:
        next_actions.append("initialize_app")
    if "kimi_key" in failed_names:
        next_actions.append("set_kimi_key")
    dependency_names = {
        "python",
        "ffmpeg",
        "ffprobe",
        "yt-dlp",
        "firefox",
        "obsidian",
        "firefox_profile",
    }
    if failed_names & dependency_names:
        next_actions.append("install_or_repair_dependencies")
    if not workspace.get("ok"):
        next_actions.append("bootstrap_workspace")
    if not zcode_models.get("ok"):
        next_actions.append("configure_zcode_model")
    next_actions.append("verify_bot_channel")
    ready_for_free_bot_test = bool(
        doctor.get("ok") and workspace.get("ok") and zcode_models.get("ok")
    )
    return {
        "schema_version": 1,
        "ok": ready_for_free_bot_test,
        "ready_for_free_bot_test": ready_for_free_bot_test,
        "paid_call_performed": False,
        "doctor": doctor,
        "workspace": workspace,
        "zcode_models": zcode_models,
        "next_actions": next_actions,
    }


def inspect_zcode_models(path: Path) -> dict[str, Any]:
    target = path.expanduser()
    if not target.is_file():
        return {
            "ok": False,
            "config_exists": False,
            "config": str(target),
            "providers": [],
            "usable_provider_count": 0,
            "has_moonshot_provider": False,
            "has_coding_plan_provider": False,
            "permissions_private": None,
            "paid_call_performed": False,
        }
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OnboardingError(f"ZCode 模型配置无法读取：{target}") from exc
    providers = payload.get("provider") if isinstance(payload, dict) else None
    if not isinstance(providers, dict):
        providers = {}

    statuses: list[ProviderStatus] = []
    for provider_id, raw in providers.items():
        if not isinstance(raw, dict):
            continue
        options = raw.get("options") if isinstance(raw.get("options"), dict) else {}
        models = raw.get("models") if isinstance(raw.get("models"), dict) else {}
        base_url = str(options.get("baseURL") or "").casefold()
        name = str(raw.get("name") or provider_id)
        folded_identity = f"{provider_id} {name} {base_url}".casefold()
        statuses.append(
            ProviderStatus(
                provider_id=str(provider_id),
                name=name,
                kind=str(raw.get("kind") or ""),
                enabled=raw.get("enabled") is not False,
                secret_present=bool(str(options.get("apiKey") or "").strip()),
                model_ids=tuple(str(item) for item in models),
                is_moonshot=("moonshot" in folded_identity or "kimi" in folded_identity),
                is_coding_plan="coding-plan" in folded_identity,
                disabled_reason_present=bool(str(raw.get("systemDisabledReason") or "").strip()),
            )
        )

    public = [status.public_payload() for status in statuses]
    usable = [status for status in statuses if status.usable_candidate]
    permissions_private: bool | None = None
    if os.name != "nt":
        permissions_private = stat.S_IMODE(target.stat().st_mode) & 0o077 == 0
    return {
        "ok": bool(usable),
        "config_exists": True,
        "config": str(target),
        "providers": public,
        "usable_provider_count": len(usable),
        "has_moonshot_provider": any(item.is_moonshot and item.usable_candidate for item in statuses),
        "has_coding_plan_provider": any(
            item.is_coding_plan and item.usable_candidate for item in statuses
        ),
        "permissions_private": permissions_private,
        "paid_call_performed": False,
    }


def build_moonshot_model_config(
    payload: dict[str, Any],
    *,
    api_key: str,
    replace_existing: bool = False,
) -> dict[str, Any]:
    """Add the documented Moonshot provider without touching unrelated providers."""

    secret = api_key.strip()
    if len(secret) < 10 or any(character.isspace() for character in secret):
        raise OnboardingError("Kimi API Key 格式无效。")
    if not isinstance(payload, dict):
        raise OnboardingError("ZCode 模型配置顶层必须是对象。")
    updated = json.loads(json.dumps(payload))
    providers = updated.setdefault("provider", {})
    if not isinstance(providers, dict):
        raise OnboardingError("ZCode 模型配置中的 provider 必须是对象。")
    entry = {
        "name": "Moonshot",
        "kind": "anthropic-compatible",
        "options": {
            "apiKey": secret,
            "baseURL": MOONSHOT_BASE_URL,
            "apiKeyRequired": True,
        },
        "source": "custom",
        "models": {
            MOONSHOT_ROUTER_MODEL: {
                "limit": {"context": 262_144, "output": 16_384},
                "modalities": {"input": ["text"], "output": ["text"]},
                "zcode": {"modified": True},
            }
        },
    }
    existing = providers.get(MOONSHOT_PROVIDER_ID)
    if existing is not None and existing != entry and not replace_existing:
        raise OnboardingError(
            "ZCode 已有不同的视知库 Moonshot 配置；拒绝静默覆盖。"
        )
    providers[MOONSHOT_PROVIDER_ID] = entry
    return updated


def configure_zcode_moonshot(
    path: Path,
    *,
    api_key: str,
    replace_existing: bool = False,
) -> dict[str, Any]:
    """Persist Moonshot only after an explicit installer/user action."""

    target = path.expanduser()
    if not target.is_file():
        raise OnboardingError(f"ZCode 模型配置不存在：{target}")
    try:
        original = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OnboardingError(f"ZCode 模型配置无法读取：{target}") from exc
    updated = build_moonshot_model_config(
        original,
        api_key=api_key,
        replace_existing=replace_existing,
    )
    backup = target.with_suffix(target.suffix + ".before-video-to-obsidian.bak")
    if not backup.exists():
        shutil.copy2(target, backup)
    if os.name != "nt":
        os.chmod(backup, 0o600)
    _atomic_json(target, updated)
    if os.name != "nt":
        os.chmod(target, 0o600)
    return {
        "ok": True,
        "configured_provider": "Moonshot",
        "configured_model": MOONSHOT_ROUTER_MODEL,
        "backup": str(backup),
        "secret_displayed": False,
        "paid_call_performed": False,
    }


def ensure_zcode_model(
    path: Path,
    *,
    api_key: str,
) -> dict[str, Any]:
    """Preserve any usable provider; add Moonshot only when ZCode has none."""

    status = inspect_zcode_models(path)
    if status["ok"]:
        return {
            "ok": True,
            "changed": False,
            "reason": "existing_provider_preserved",
            "usable_provider_count": status["usable_provider_count"],
            "secret_displayed": False,
            "paid_call_performed": False,
        }
    if not status["config_exists"]:
        return {
            "ok": False,
            "changed": False,
            "reason": "zcode_not_initialized",
            "secret_displayed": False,
            "paid_call_performed": False,
        }
    configured = configure_zcode_moonshot(path, api_key=api_key)
    return {
        **configured,
        "changed": True,
        "reason": "moonshot_added",
    }
