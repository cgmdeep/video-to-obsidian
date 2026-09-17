"""One-attempt Kimi video analysis with a mockable transport boundary."""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Protocol

import httpx

from .config import Settings
from .errors import AppError


DEFAULT_INSTRUCTION = (
    "请用中文认真、完整、忠实地总结视频本身，并直接写成可入库的正式知识库笔记；"
    "保留视频的论证顺序、例子、数据、画面信息和结论。不要添加外部背景、事实核查、"
    "可信度裁决或模型自己的评价。"
)
_TOPIC_LINE = re.compile(r"^\s*主题标签\s*[:：]\s*(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class KimiResult:
    body: str
    topic_tags: tuple[str, ...]
    warnings: tuple[str, ...]
    diagnostics: dict[str, Any]


class KimiTransport(Protocol):
    def upload_video(self, video_path: Path, mime: str) -> str: ...

    def stream_chat(self, payload: dict[str, Any]) -> Iterable[dict[str, Any]]: ...

    def delete_file(self, file_id: str) -> str: ...


class HttpxKimiTransport:
    def __init__(self, *, api_key: str, base_url: str, timeout_seconds: int) -> None:
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    def upload_video(self, video_path: Path, mime: str) -> str:
        try:
            with httpx.Client(timeout=self._timeout) as client, video_path.open("rb") as handle:
                response = client.post(
                    f"{self._base_url}/files",
                    headers=self._headers,
                    files={"file": (video_path.name, handle, mime)},
                    data={"purpose": "video"},
                )
        except Exception as exc:
            raise AppError(
                "kimi_transport_failed",
                "连接 Kimi 上传视频失败。",
                retryable=True,
                details={"phase": "upload", "kimi_attempts": 0},
            ) from exc
        _raise_for_kimi_status(response.status_code, phase="upload", attempts=0)
        try:
            file_id = str(response.json()["id"]).strip()
        except (KeyError, TypeError, ValueError) as exc:
            raise AppError(
                "kimi_invalid_response",
                "Kimi 上传响应缺少文件 ID。",
                details={"phase": "upload", "kimi_attempts": 0},
            ) from exc
        if not file_id:
            raise AppError(
                "kimi_invalid_response",
                "Kimi 上传响应缺少文件 ID。",
                details={"phase": "upload", "kimi_attempts": 0},
            )
        return file_id

    def stream_chat(self, payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
        try:
            with httpx.Client(timeout=self._timeout) as client, client.stream(
                "POST",
                f"{self._base_url}/chat/completions",
                headers={**self._headers, "Content-Type": "application/json"},
                json=payload,
            ) as response:
                _raise_for_kimi_status(response.status_code, phase="analysis", attempts=1)
                saw_data = False
                for raw_line in response.iter_lines():
                    line = str(raw_line or "").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except (TypeError, ValueError) as exc:
                        raise AppError(
                            "kimi_invalid_response",
                            "Kimi 流式响应包含无效 JSON。",
                            details={"phase": "analysis", "kimi_attempts": 1},
                        ) from exc
                    if not isinstance(chunk, dict):
                        raise AppError(
                            "kimi_invalid_response",
                            "Kimi 流式响应结构无效。",
                            details={"phase": "analysis", "kimi_attempts": 1},
                        )
                    saw_data = True
                    yield chunk
                if not saw_data:
                    raise AppError(
                        "kimi_invalid_response",
                        "Kimi 没有返回可解析的流式数据。",
                        details={"phase": "analysis", "kimi_attempts": 1},
                    )
        except AppError:
            raise
        except Exception as exc:
            raise AppError(
                "kimi_transport_failed",
                "连接 Kimi 视频分析失败。",
                retryable=True,
                details={"phase": "analysis", "kimi_attempts": 1},
            ) from exc

    def delete_file(self, file_id: str) -> str:
        if not file_id:
            return ""
        try:
            with httpx.Client(timeout=60) as client:
                response = client.delete(
                    f"{self._base_url}/files/{file_id}", headers=self._headers
                )
            if response.status_code not in {200, 204, 404}:
                return f"Kimi 临时文件清理返回 HTTP {response.status_code}。"
        except Exception:
            return "Kimi 临时文件清理失败。"
        return ""


def _raise_for_kimi_status(status_code: int, *, phase: str, attempts: int) -> None:
    details = {"phase": phase, "kimi_attempts": attempts, "http_status": status_code}
    if status_code == 429:
        raise AppError(
            "kimi_rate_limited",
            "Kimi 请求触发限流（HTTP 429）。",
            retryable=True,
            details=details,
        )
    if status_code >= 500:
        raise AppError(
            "kimi_upstream_failed",
            f"Kimi 服务异常：HTTP {status_code}。",
            retryable=True,
            details=details,
        )
    allowed = {200, 201} if phase == "upload" else {200}
    if status_code not in allowed:
        code = "kimi_upload_failed" if phase == "upload" else "kimi_request_rejected"
        raise AppError(code, f"Kimi 请求被拒绝：HTTP {status_code}。", details=details)


def _numeric_only(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): cleaned
            for key, item in value.items()
            if (cleaned := _numeric_only(item)) is not None
        }
    if isinstance(value, list):
        return [cleaned for item in value if (cleaned := _numeric_only(item)) is not None]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    return None


def _text_length(value: Any) -> int:
    if isinstance(value, str):
        return len(value)
    if value is None:
        return 0
    try:
        return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
    except (TypeError, ValueError):
        return len(str(value))


def _clean_body(text: str) -> tuple[str, tuple[str, ...]]:
    body = text or ""
    match = _TOPIC_LINE.search(body)
    tags: list[str] = []
    if match:
        tags = [item.strip() for item in re.split(r"[,，、]", match.group(1)) if item.strip()]
        body = (body[: match.start()] + body[match.end() :]).rstrip()
    lines = body.splitlines()
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        if line.startswith("# "):
            lines.pop(index)
        break
    return "\n".join(lines).strip(), tuple(dict.fromkeys(tags))[:8]


def _prompt(metadata: dict[str, Any], instruction: str, *, is_proxy: bool) -> str:
    tags = " ".join(f"#{item}" for item in metadata.get("tags", []))
    text = (
        f"平台：{metadata.get('platform', '')}\n"
        f"标题：{metadata.get('title', '')}\n"
        f"作者：{metadata.get('uploader', '')}\n"
        f"话题：{tags}\n"
        f"时长：{metadata.get('duration', 0)}秒\n"
        f"当前日期：{datetime.now().astimezone().strftime('%Y-%m-%d')}\n\n"
        f"用户要求：{instruction.strip() or DEFAULT_INSTRUCTION}\n\n"
        "请直接观看整段视频的画面、烧屏字幕、图表、演示和音频，并由你直接写成正式中文知识库笔记。"
        "正文必须使用 Markdown，并按以下三级标题组织：\n"
        "### 内容速览\n### 详细内容梳理\n### 视频结论\n"
        "只忠实总结视频本身，完整保留论证顺序、例子、数据、画面信息和结论。"
        "必须区分作者的字面陈述、引用或模仿他人观点、反讽、戏仿、夸张和反问；"
        "不要把反话、作者批评的引述或表演性模仿写成作者自己的结论。"
        "判断反讽时同时核对语气、前后文、字幕与画面；证据不足时写‘疑似反讽’，不要强行确定。"
        "不添加外部背景、事实核查、可信度裁决、道德评价或延伸评论。"
        "未经核验的陈述使用‘视频称/作者认为/视频举例’等归属表达。"
        "程序会按需附加 SenseVoice 逐字稿，你不要生成、复述或改写逐字稿。\n"
        "最后另起一行，以 `主题标签: ` 开头，给出3到5个中文主题词，逗号分隔。"
    )
    if is_proxy:
        text += "\n输入是覆盖完整时间线的低码率代理，没有裁剪时间线，请按整段视频分析。"
    return text


class KimiVideoClient:
    def __init__(
        self,
        settings: Settings,
        *,
        api_key: str | None = None,
        transport: KimiTransport | None = None,
        upload_threshold_bytes: int = 8 * 1024 * 1024,
    ) -> None:
        self.settings = settings
        self.api_key = (api_key if api_key is not None else os.environ.get("KIMI_API_KEY", "")).strip()
        self.upload_threshold_bytes = upload_threshold_bytes
        self.transport = transport or HttpxKimiTransport(
            api_key=self.api_key,
            base_url=settings.kimi_base_url,
            timeout_seconds=settings.kimi_timeout_seconds,
        )

    def analyze(
        self,
        video_path: Path,
        metadata: dict[str, Any],
        *,
        mode: str = "vision",
        instruction: str = "",
        is_proxy: bool = False,
    ) -> KimiResult:
        if not self.api_key:
            raise AppError("missing_kimi_key", "未配置 KIMI_API_KEY，无法执行视频分析。")
        if mode not in {"vision", "deep"}:
            raise AppError("unsupported_mode", "分析档位只能是 vision 或 deep。")
        if not video_path.is_file() or video_path.stat().st_size <= 0:
            raise AppError("missing_video_file", "Kimi 输入视频不存在或为空。")

        model = self.settings.deep_model if mode == "deep" else self.settings.default_model
        max_tokens = self.settings.deep_max_tokens if mode == "deep" else self.settings.vision_max_tokens
        mime = mimetypes.guess_type(video_path.name)[0] or "video/mp4"
        file_id = ""
        warnings: list[str] = []
        completed: KimiResult | None = None
        try:
            if video_path.stat().st_size <= self.upload_threshold_bytes:
                encoded = base64.b64encode(video_path.read_bytes()).decode("ascii")
                reference = f"data:{mime};base64,{encoded}"
            else:
                file_id = self.transport.upload_video(video_path, mime)
                reference = f"ms://{file_id}"
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "video_url", "video_url": {"url": reference}},
                            {"type": "text", "text": _prompt(metadata, instruction, is_proxy=is_proxy)},
                        ],
                    }
                ],
                "max_completion_tokens": max_tokens,
                "stream": True,
                "stream_options": {"include_usage": True},
            }
            content_parts: list[str] = []
            reasoning_chars = 0
            refusal_chars = 0
            finish_reason = ""
            usage: dict[str, Any] = {}
            saw_chunk = False
            for chunk in self.transport.stream_chat(payload):
                if not isinstance(chunk, dict):
                    raise AppError(
                        "kimi_invalid_response",
                        "Kimi 流式响应结构无效。",
                        details={"phase": "analysis", "kimi_attempts": 1},
                    )
                saw_chunk = True
                numeric = _numeric_only(chunk.get("usage"))
                if isinstance(numeric, dict) and numeric:
                    usage = numeric
                choices = chunk.get("choices")
                if not isinstance(choices, list) or not choices:
                    continue
                choice = choices[0]
                if not isinstance(choice, dict):
                    raise AppError(
                        "kimi_invalid_response",
                        "Kimi choice 结构无效。",
                        details={"phase": "analysis", "kimi_attempts": 1},
                    )
                if choice.get("finish_reason") is not None:
                    finish_reason = str(choice.get("finish_reason") or "")
                delta = choice.get("delta") if isinstance(choice.get("delta"), dict) else {}
                content = delta.get("content")
                if content is not None and not isinstance(content, str):
                    raise AppError(
                        "kimi_invalid_response",
                        "Kimi 正文不是文本格式。",
                        details={"phase": "analysis", "kimi_attempts": 1},
                    )
                if content:
                    content_parts.append(content)
                reasoning_chars += sum(
                    _text_length(delta.get(key))
                    for key in ("reasoning_content", "reasoning", "reasoning_details")
                )
                refusal_chars += _text_length(delta.get("refusal"))
            if not saw_chunk:
                raise AppError(
                    "kimi_invalid_response",
                    "Kimi 没有返回可解析的流式数据。",
                    details={"phase": "analysis", "kimi_attempts": 1},
                )
            body, topic_tags = _clean_body("".join(content_parts))
            diagnostics = {
                "retryable": False,
                "kimi_attempts": 1,
                "finish_reason": finish_reason,
                "usage": usage,
                "content_chars": len(body),
                "reasoning_chars": reasoning_chars,
                "refusal_chars": refusal_chars,
                "model": model,
                "max_completion_tokens": max_tokens,
            }
            lowered_reason = finish_reason.lower()
            if refusal_chars or lowered_reason in {"content_filter", "safety", "refusal"}:
                raise AppError("kimi_model_refused", "Kimi 未提供正式笔记正文。", details=diagnostics)
            if lowered_reason == "length":
                raise AppError(
                    "kimi_output_budget_exhausted",
                    "Kimi 输出预算耗尽，未形成完整的正式笔记正文。",
                    details=diagnostics,
                )
            if len(body) < 80:
                raise AppError(
                    "kimi_empty_response",
                    "Kimi 正常结束但没有返回足够的正式笔记正文。",
                    details=diagnostics,
                )
            completed = KimiResult(body, topic_tags, (), diagnostics)
        finally:
            if file_id:
                warning = self.transport.delete_file(file_id)
                if warning:
                    warnings.append(warning)
        if completed is None:  # pragma: no cover - exceptions leave through the try block
            raise AppError("kimi_invalid_response", "Kimi 未形成可用结果。")
        return KimiResult(
            completed.body,
            completed.topic_tags,
            tuple(warnings),
            completed.diagnostics,
        )
