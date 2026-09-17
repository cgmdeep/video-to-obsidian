"""Single public MCP entry point."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .doctor import doctor_payload
from .routing import RoutingError, route_share_text


mcp = FastMCP("video-to-obsidian")


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


def run() -> None:
    mcp.run()

