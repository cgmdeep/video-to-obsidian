"""Command-line interface for setup, diagnostics and MCP startup."""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path

from . import __version__
from .config import ConfigError, initialize_settings, load_settings
from .doctor import doctor_payload
from .preferences import (
    PreferenceError,
    clear_preferences,
    read_preferences,
    write_preferences,
)
from .routing import RoutingError, route_share_text
from .zcode import ZCodeConfigError
from .secrets import SecretError, delete_kimi_api_key, kimi_key_source, set_kimi_api_key


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="video-to-obsidian")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="创建公共配置和 Vault 子目录")
    init.add_argument("--vault", type=Path, required=True)
    init.add_argument("--profile", choices=("standard", "transcript"), default="standard")
    init.add_argument("--save-video", action="store_true")
    init.add_argument("--config", type=Path)
    init.add_argument("--overwrite", action="store_true")
    init.add_argument("--reuse-existing", action="store_true")

    doctor = sub.add_parser("doctor", help="免费环境体检")
    doctor.add_argument("--config", type=Path)
    doctor.add_argument("--json", action="store_true")

    route = sub.add_parser("route", help="只识别视频平台和分析档位")
    route.add_argument("share_text")
    route.add_argument("--save-video", action="store_true")

    sub.add_parser("mcp", help="以 stdio 启动统一 MCP")

    zcode = sub.add_parser("configure-zcode", help="安全增量配置 ZCode stdio MCP")
    zcode.add_argument(
        "--config",
        type=Path,
        default=Path.home() / ".zcode" / "cli" / "config.json",
    )
    zcode.add_argument("--timeout-ms", type=int, default=1_200_000)
    zcode.add_argument("--replace-existing", action="store_true")

    remove = sub.add_parser("unconfigure-zcode", help="只删除本项目的 ZCode MCP 条目")
    remove.add_argument(
        "--config",
        type=Path,
        default=Path.home() / ".zcode" / "cli" / "config.json",
    )

    sub.add_parser("set-kimi-key", help="无回显地把 Kimi API Key 保存到系统钥匙串")
    sub.add_parser("delete-kimi-key", help="从系统钥匙串删除 Kimi API Key")
    sub.add_parser("kimi-key-status", help="只显示 Key 来源，不显示值")

    set_preferences = sub.add_parser("set-summary-preferences", help="保存长期总结偏好")
    set_preferences.add_argument("text", nargs="+")
    set_preferences.add_argument("--config", type=Path)

    show_preferences = sub.add_parser("show-summary-preferences", help="查看长期总结偏好")
    show_preferences.add_argument("--config", type=Path)

    clear_preferences_parser = sub.add_parser(
        "clear-summary-preferences", help="清除长期总结偏好"
    )
    clear_preferences_parser.add_argument("--config", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "init":
            path = initialize_settings(
                args.vault,
                profile=args.profile,
                save_video=args.save_video,
                config_path=args.config,
                overwrite=args.overwrite,
                reuse_existing=args.reuse_existing,
            )
            print(f"配置已创建：{path}")
            return 0
        if args.command == "doctor":
            payload = doctor_payload(args.config)
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                for item in payload["checks"]:
                    flag = "OK" if item["ok"] else ("FAIL" if item["required"] else "WARN")
                    print(f"[{flag}] {item['name']}: {item['detail']}")
            return 0 if payload["ok"] else 1
        if args.command == "route":
            print(json.dumps(route_share_text(args.share_text, save_video=args.save_video).to_dict(), ensure_ascii=False, indent=2))
            return 0
        if args.command == "mcp":
            from .server import run

            run()
            return 0
        if args.command == "configure-zcode":
            from .zcode import update_file

            backup = update_file(
                args.config,
                command=sys.executable,
                args=["-m", "video_to_obsidian", "mcp"],
                timeout_ms=args.timeout_ms,
                replace_existing=args.replace_existing,
            )
            print(f"ZCode 已配置；恢复副本：{backup}")
            return 0
        if args.command == "unconfigure-zcode":
            from .zcode import remove_from_file

            backup = remove_from_file(args.config)
            print(f"已移除本项目 ZCode 条目；恢复副本：{backup}")
            return 0
        if args.command == "set-kimi-key":
            first = getpass.getpass("请输入 Kimi API Key（不会回显）：")
            second = getpass.getpass("请再次输入：")
            if first != second:
                raise SecretError("两次输入不一致，未保存。")
            set_kimi_api_key(first)
            print("Kimi API Key 已保存到系统钥匙串（值未显示）。")
            return 0
        if args.command == "delete-kimi-key":
            removed = delete_kimi_api_key()
            print("已从系统钥匙串删除。" if removed else "系统钥匙串中没有本项目的 Kimi Key。")
            return 0
        if args.command == "kimi-key-status":
            print(f"Kimi API Key 来源：{kimi_key_source()}（值未显示）")
            return 0
        if args.command == "set-summary-preferences":
            settings = load_settings(args.config)
            path = write_preferences(settings, " ".join(args.text))
            print(f"长期总结偏好已保存：{path}")
            return 0
        if args.command == "show-summary-preferences":
            settings = load_settings(args.config)
            preferences = read_preferences(settings)
            print(preferences if preferences else "当前未设置长期总结偏好。")
            return 0
        if args.command == "clear-summary-preferences":
            settings = load_settings(args.config)
            removed = clear_preferences(settings)
            print("长期总结偏好已清除。" if removed else "当前没有长期总结偏好。")
            return 0
    except (ConfigError, RoutingError, ZCodeConfigError, SecretError, PreferenceError) as exc:
        print(f"错误：{exc}")
        return 2
    return 2
