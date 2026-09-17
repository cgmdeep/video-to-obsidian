"""Single public MCP entry point."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

import asyncio

from .config import ConfigError, load_settings
from .doctor import doctor_payload
from .errors import AppError
from .pipeline import analyze_bilibili as run_bilibili_pipeline
from .routing import RoutingError, route_share_text


mcp = FastMCP("video-to-obsidian")
_ANALYZE_SEMAPHORE = asyncio.Semaphore(1)


@mcp.tool()
def doctor() -> dict[str, object]:
    """免费检查本机依赖、公共配置和 Vault；不显示密钥、不调用付费视频分析。"""
    return doctor_payload()


@mcp.tool()
def route_video(share_text: str, save_video: bool = False) -> dict[str, object]:
    """只识别平台、档位和归档意图，不下载视频、不调用 Kimi。"""
    try:
        decision = route_share_text(share_text, save_video=save_video)
        return {"ok": True, **decision.to_dict(), "paid_call_performed": False}
    except RoutingError as exc:
        return {
            "ok": False,
            "error_code": "route_failed",
            "error": str(exc),
            "retryable": False,
            "paid_call_performed": False,
        }


@mcp.tool()
async def analyze_bilibili(
    share_text: str,
    mode: str = "vision",
    instruction: str = "",
    save_video: bool = False,
) -> dict[str, object]:
    """分析一条B站普通单视频并写入 Obsidian；默认不保存原视频。"""
    try:
        settings = load_settings()
        async with _ANALYZE_SEMAPHORE:
            return await asyncio.to_thread(
                run_bilibili_pipeline,
                share_text,
                settings=settings,
                mode=mode,
                instruction=instruction,
                save_video=save_video,
            )
    except ConfigError as exc:
        return AppError("invalid_config", str(exc)).payload()
    except AppError as exc:
        return exc.payload()
    except Exception:
        return AppError(
            "internal_error",
            "B站分析服务发生内部错误；详细信息未写入MCP返回。",
        ).payload()


def run() -> None:
    mcp.run()
