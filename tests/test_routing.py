import pytest

from video_to_obsidian.routing import RoutingError, route_share_text


def test_routes_douyin_share_text() -> None:
    decision = route_share_text("复制打开抖音 https://v.douyin.com/abc123/")
    assert decision.platform == "douyin"
    assert decision.mode == "vision"
    assert decision.save_video is False


def test_only_exact_k3_phrase_enables_deep() -> None:
    assert route_share_text("BV1Uw826pE7J 仔细深度分析").mode == "vision"
    assert route_share_text("BV1Uw826pE7J 使用K3深度分析").mode == "deep"


def test_rejects_mixed_platforms() -> None:
    with pytest.raises(RoutingError):
        route_share_text("https://v.douyin.com/a/ https://b23.tv/b/")


def test_rejects_unknown_text() -> None:
    with pytest.raises(RoutingError):
        route_share_text("今天吃什么")

