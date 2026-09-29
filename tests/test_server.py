import asyncio
import threading
import time

import pytest

from video_to_obsidian.errors import AppError
from video_to_obsidian import server


@pytest.mark.parametrize(
    ("tool_name", "pipeline_name"),
    (("analyze_bilibili", "run_bilibili_pipeline"), ("analyze_douyin", "run_douyin_pipeline")),
)
def test_mcp_failure_payload_never_claims_saved_or_archived(
    monkeypatch: pytest.MonkeyPatch,
    tool_name: str,
    pipeline_name: str,
) -> None:
    monkeypatch.setattr(server, "load_settings", lambda: object())
    monkeypatch.setattr(
        server,
        pipeline_name,
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AppError(
                "kimi_rate_limited",
                "Kimi 请求触发限流（HTTP 429）。",
                retryable=True,
                details={"phase": "analysis", "http_status": 429, "kimi_attempts": 1},
            )
        ),
    )

    payload = asyncio.run(getattr(server, tool_name)("share text"))

    assert payload["ok"] is False
    assert payload["complete"] is False
    assert payload["status"] == "failed"
    assert payload["retryable"] is True
    assert payload["details"]["kimi_attempts"] == 1
    assert "saved_to" not in payload
    assert "archived_video" not in payload


def test_unexpected_mcp_failure_is_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "load_settings", lambda: object())
    monkeypatch.setattr(
        server,
        "run_bilibili_pipeline",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("secret provider response must not escape")
        ),
    )

    payload = asyncio.run(server.analyze_bilibili("share text"))

    assert payload == {
        "ok": False,
        "complete": False,
        "status": "failed",
        "error_code": "internal_error",
        "error": "B站分析服务发生内部错误；详细信息未写入MCP返回。",
        "retryable": False,
        "details": {"retryable": False},
    }


def test_one_hundred_mcp_submissions_are_serialized_without_paid_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(server, "load_settings", lambda: object())
    monkeypatch.setattr(server, "_ANALYZE_SEMAPHORE", asyncio.Semaphore(1))
    lock = threading.Lock()
    active = 0
    maximum_active = 0
    completed = 0

    def fake_pipeline(*args, **kwargs):
        nonlocal active, maximum_active, completed
        with lock:
            active += 1
            maximum_active = max(maximum_active, active)
        time.sleep(0.001)
        with lock:
            active -= 1
            completed += 1
        return {"ok": True, "paid_call_performed": False}

    monkeypatch.setattr(server, "run_bilibili_pipeline", fake_pipeline)

    async def run_soak() -> list[dict[str, object]]:
        return await asyncio.gather(
            *(server.analyze_bilibili(f"BV test {index}") for index in range(100))
        )

    results = asyncio.run(run_soak())

    assert completed == 100
    assert maximum_active == 1
    assert all(item == {"ok": True, "paid_call_performed": False} for item in results)
