from pathlib import Path

import pytest

from video_to_obsidian.config import initialize_settings, load_settings
from video_to_obsidian.errors import AppError
from video_to_obsidian.kimi import KimiVideoClient


class FakeTransport:
    def __init__(self, chunks):
        self.chunks = chunks
        self.uploads = 0
        self.streams = 0
        self.deleted = []
        self.payload = None

    def upload_video(self, video_path: Path, mime: str) -> str:
        self.uploads += 1
        return "file-123"

    def stream_chat(self, payload):
        self.streams += 1
        self.payload = payload
        yield from self.chunks

    def delete_file(self, file_id: str) -> str:
        self.deleted.append(file_id)
        return ""


def _settings(tmp_path: Path):
    config = initialize_settings(
        tmp_path / "vault",
        config_path=tmp_path / "config.toml",
        runtime_root=tmp_path / "private",
    )
    return load_settings(config)


def _video(tmp_path: Path) -> Path:
    path = tmp_path / "video.mp4"
    path.write_bytes(b"video-data")
    return path


def test_one_kimi_call_and_cleanup(tmp_path: Path) -> None:
    body = "### 内容速览\n" + "这是完整内容。" * 20
    transport = FakeTransport(
        [
            {"choices": [{"delta": {"reasoning_content": "思考"}}]},
            {"choices": [{"delta": {"content": body + "\n主题标签: 测试，知识"}}]},
            {
                "choices": [{"delta": {}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 200, "text": "drop"},
            },
        ]
    )
    result = KimiVideoClient(
        _settings(tmp_path),
        api_key="test-key",
        transport=transport,
        upload_threshold_bytes=1,
    ).analyze(
        _video(tmp_path),
        {"platform": "bilibili", "title": "测试", "duration": 60, "tags": []},
    )
    assert transport.uploads == 1
    assert transport.streams == 1
    assert transport.deleted == ["file-123"]
    assert result.topic_tags == ("测试", "知识")
    assert result.diagnostics["reasoning_chars"] == 2
    assert result.diagnostics["usage"] == {"prompt_tokens": 100, "completion_tokens": 200}


def test_exact_deep_mode_uses_k3_and_16k(tmp_path: Path) -> None:
    transport = FakeTransport(
        [
            {"choices": [{"delta": {"content": "正文" * 50}}]},
            {"choices": [{"delta": {}, "finish_reason": "stop"}]},
        ]
    )
    KimiVideoClient(
        _settings(tmp_path), api_key="test-key", transport=transport
    ).analyze(_video(tmp_path), {"title": "x"}, mode="deep")
    assert transport.payload["model"] == "kimi-k3"
    assert transport.payload["max_completion_tokens"] == 16000


def test_length_is_non_retryable_and_file_is_deleted(tmp_path: Path) -> None:
    transport = FakeTransport(
        [
            {"choices": [{"delta": {"content": "截断正文" * 50}}]},
            {"choices": [{"delta": {}, "finish_reason": "length"}]},
        ]
    )
    client = KimiVideoClient(
        _settings(tmp_path),
        api_key="test-key",
        transport=transport,
        upload_threshold_bytes=1,
    )
    with pytest.raises(AppError) as caught:
        client.analyze(_video(tmp_path), {"title": "x"})
    assert caught.value.code == "kimi_output_budget_exhausted"
    assert caught.value.retryable is False
    assert transport.streams == 1
    assert transport.deleted == ["file-123"]


def test_missing_key_stops_before_transport(tmp_path: Path) -> None:
    transport = FakeTransport([])
    client = KimiVideoClient(_settings(tmp_path), api_key="", transport=transport)
    with pytest.raises(AppError) as caught:
        client.analyze(_video(tmp_path), {"title": "x"})
    assert caught.value.code == "missing_kimi_key"
    assert transport.streams == 0


def test_prompt_contains_irony_guard(tmp_path: Path) -> None:
    transport = FakeTransport(
        [
            {"choices": [{"delta": {"content": "正文" * 50}}]},
            {"choices": [{"delta": {}, "finish_reason": "stop"}]},
        ]
    )
    KimiVideoClient(
        _settings(tmp_path), api_key="test-key", transport=transport
    ).analyze(_video(tmp_path), {"title": "x"})
    prompt = transport.payload["messages"][0]["content"][1]["text"]
    assert "反讽" in prompt
    assert "疑似反讽" in prompt
