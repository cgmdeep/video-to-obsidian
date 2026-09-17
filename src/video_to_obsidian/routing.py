"""Pure routing logic; no network or paid model calls."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass


DEEP_TRIGGER = "使用K3深度分析"
_DOUYIN = re.compile(r"(?:https?://)?(?:v\.)?douyin\.com/", re.IGNORECASE)
_BILIBILI = re.compile(
    r"(?:https?://)?(?:www\.)?(?:bilibili\.com/video/|b23\.tv/)|(?<![A-Za-z0-9])BV[1-9A-HJ-NP-Za-km-z]{10}(?![A-Za-z0-9])",
    re.IGNORECASE,
)


class RoutingError(ValueError):
    """Raised when a share text cannot be routed safely."""


@dataclass(frozen=True)
class RouteDecision:
    platform: str
    mode: str
    save_video: bool
    deep_trigger_found: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def route_share_text(share_text: str, *, save_video: bool = False) -> RouteDecision:
    text = (share_text or "").strip()
    if not text:
        raise RoutingError("分享文本不能为空。")
    douyin = bool(_DOUYIN.search(text))
    bilibili = bool(_BILIBILI.search(text))
    if douyin and bilibili:
        raise RoutingError("同一条消息同时包含抖音和B站链接，拒绝猜测。")
    if not douyin and not bilibili:
        raise RoutingError("没有识别到抖音或B站单视频标识。")
    deep = DEEP_TRIGGER in text
    return RouteDecision(
        platform="douyin" if douyin else "bilibili",
        mode="deep" if deep else "vision",
        save_video=bool(save_video),
        deep_trigger_found=deep,
    )

