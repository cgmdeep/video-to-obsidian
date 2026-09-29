"""Run the deterministic quality fixture through Kimi exactly once.

This is an acceptance-only command.  It deliberately keeps the generated body
outside the Vault, leaves a durable one-shot lock before contacting Kimi, and
never retries a failed provider call.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from video_to_obsidian.config import load_settings
from video_to_obsidian.errors import AppError
from video_to_obsidian.kimi import KimiVideoClient
from video_to_obsidian.secrets import kimi_key_source
from video_to_obsidian.state import write_json


EXPECTED_SHA256 = "bdbd8234162f2bd1de463e834eda1d80415c09884c8f4e9e00e26e8a42645d3c"
INPUT_PRICE_CNY_PER_MILLION = 6.50
OUTPUT_PRICE_CNY_PER_MILLION = 27.00


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _integer(value: Any) -> int:
    return int(value) if isinstance(value, (int, float)) and value >= 0 else 0


def _usage_cost(usage: dict[str, Any]) -> tuple[dict[str, int], float]:
    prompt = _integer(usage.get("prompt_tokens"))
    completion = _integer(usage.get("completion_tokens"))
    normalized = {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": _integer(usage.get("total_tokens")) or prompt + completion,
    }
    estimate = (
        prompt * INPUT_PRICE_CNY_PER_MILLION
        + completion * OUTPUT_PRICE_CNY_PER_MILLION
    ) / 1_000_000
    return normalized, round(estimate, 6)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--body-output", type=Path)
    parser.add_argument("--approved-max-calls", type=int, required=True)
    parser.add_argument("--approved-budget-cny", type=float, required=True)
    parser.add_argument("--call-index", type=int, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not 1 <= args.call_index <= args.approved_max_calls <= 3:
        raise SystemExit("approved call boundary must be within 1..3")
    if not 0 < args.approved_budget_cny <= 2:
        raise SystemExit("approved budget must be greater than 0 and no more than CNY 2")

    settings = load_settings(args.config)
    if settings.default_model != "kimi-k2.7-code":
        raise SystemExit("quality fixture acceptance requires kimi-k2.7-code")
    fixture = args.fixture.resolve()
    if not fixture.is_file() or _sha256(fixture) != EXPECTED_SHA256:
        raise SystemExit("fixture is missing or its SHA256 does not match the frozen set")

    directory = settings.paths.state / "acceptance"
    output = args.output or directory / "quality-fixed-set-v1-k27.json"
    body_output = args.body_output or directory / "quality-fixed-set-v1-k27.md"
    lock = output.with_suffix(output.suffix + ".started")
    if output.exists() or body_output.exists() or lock.exists():
        raise SystemExit("this acceptance call has already been started; refusing to rerun")
    output.parent.mkdir(parents=True, exist_ok=True)
    body_output.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise SystemExit("this acceptance call has already been started; refusing to rerun") from exc
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"started_at": _now(), "call_index": args.call_index}, handle)
        handle.write("\n")

    key_source = kimi_key_source()
    report: dict[str, Any] = {
        "schema_version": 1,
        "kind": "quality_fixture_acceptance",
        "identity": "quality-fixed-set-v1",
        "fixture_sha256": EXPECTED_SHA256,
        "started_at": _now(),
        "status": "running",
        "model": settings.default_model,
        "call_index": args.call_index,
        "approved_max_calls": args.approved_max_calls,
        "approved_budget_cny": args.approved_budget_cny,
        "key_source": key_source,
        "provider_attempts": 0,
        "paid_call_performed": False,
    }
    write_json(output, report)
    if key_source not in {"environment", "keyring"}:
        report.update({"status": "failed_preflight", "finished_at": _now(), "error_code": "missing_kimi_key"})
        write_json(output, report)
        return 2

    metadata = {
        "platform": "quality-fixture",
        "title": "视知库总结质量固定集 v1",
        "uploader": "未竟实验（离线合成）",
        "duration": 85.966,
        "identity": "quality-fixed-set-v1",
        "tags": ["多人观点", "反讽", "音画冲突", "引用归属"],
    }
    report["provider_attempts"] = 1
    report["paid_call_performed"] = True
    write_json(output, report)
    try:
        result = KimiVideoClient(settings).analyze(
            fixture,
            metadata,
            instruction=(
                "严格按视频内容生成正式笔记；尤其不要遗漏任何发言人、"
                "数字冲突、反讽及引用关系。"
            ),
        )
        usage, estimate = _usage_cost(dict(result.diagnostics.get("usage") or {}))
        if estimate > args.approved_budget_cny:
            status = "completed_over_budget"
        else:
            status = "completed"
        body_output.write_text(result.body.rstrip() + "\n", encoding="utf-8", newline="\n")
        report.update(
            {
                "status": status,
                "finished_at": _now(),
                "finish_reason": str(result.diagnostics.get("finish_reason") or ""),
                "usage": usage,
                "estimated_cost_cny": estimate,
                "price_basis": {
                    "input_cny_per_million": INPUT_PRICE_CNY_PER_MILLION,
                    "output_cny_per_million": OUTPUT_PRICE_CNY_PER_MILLION,
                    "cache_assumption": "all_prompt_tokens_cache_miss",
                },
                "content_chars": len(result.body),
                "topic_tag_count": len(result.topic_tags),
                "warning_count": len(result.warnings),
                "body_output": str(body_output),
            }
        )
        write_json(output, report)
        print(output)
        return 0 if status == "completed" else 3
    except AppError as exc:
        report.update(
            {
                "status": "failed",
                "finished_at": _now(),
                "error_code": exc.code,
                "retryable": False,
            }
        )
        usage, estimate = _usage_cost(dict(exc.details.get("usage") or {}))
        if any(usage.values()):
            report["usage"] = usage
            report["estimated_cost_cny"] = estimate
        write_json(output, report)
        return 1
    except Exception as exc:  # never persist provider response text or secrets
        report.update(
            {
                "status": "failed",
                "finished_at": _now(),
                "error_code": f"internal_{type(exc).__name__}",
                "retryable": False,
            }
        )
        write_json(output, report)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
