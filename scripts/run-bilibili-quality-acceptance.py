"""Run one frozen public Bilibili quality sample without provider retries."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from video_to_obsidian.config import load_settings
from video_to_obsidian.errors import AppError
from video_to_obsidian.pipeline import analyze_bilibili
from video_to_obsidian.state import write_json


INPUT_PRICE_CNY_PER_MILLION = 6.50
OUTPUT_PRICE_CNY_PER_MILLION = 27.00


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


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


def _history_count(settings: Any, identity: str) -> int:
    directory = settings.paths.state / "history" / "bilibili" / identity
    return len(list(directory.glob("*.json"))) if directory.is_dir() else 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("bvid")
    parser.add_argument("--identity", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--instruction", required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--approved-max-calls", type=int, required=True)
    parser.add_argument("--approved-budget-cny", type=float, required=True)
    parser.add_argument("--call-index", type=int, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not 1 <= args.call_index <= args.approved_max_calls <= 3:
        raise SystemExit("approved call boundary must be within 1..3")
    if not 0 < args.approved_budget_cny <= 2:
        raise SystemExit("remaining approved budget must be greater than 0 and no more than CNY 2")
    if not args.bvid.startswith("BV") or args.identity != f"bilibili_{args.bvid}_p01":
        raise SystemExit("frozen BVID and identity do not match")

    settings = load_settings(args.config)
    if settings.default_model != "kimi-k2.7-code":
        raise SystemExit("quality acceptance requires kimi-k2.7-code")
    output = args.output or settings.paths.state / "acceptance" / f"{args.label}-k27.json"
    lock = output.with_suffix(output.suffix + ".started")
    manifest = settings.paths.state / "bilibili" / f"{args.identity}.json"
    history_before = _history_count(settings, args.identity)
    if output.exists() or lock.exists() or manifest.exists() or history_before:
        raise SystemExit("sample has prior state or this acceptance has already started")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise SystemExit("this acceptance has already started") from exc
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"started_at": _now(), "call_index": args.call_index}, handle)
        handle.write("\n")

    report: dict[str, Any] = {
        "schema_version": 1,
        "kind": "public_bilibili_quality_acceptance",
        "label": args.label,
        "identity": args.identity,
        "started_at": _now(),
        "status": "running",
        "model": settings.default_model,
        "call_index": args.call_index,
        "approved_max_calls": args.approved_max_calls,
        "remaining_approved_budget_cny": args.approved_budget_cny,
        "history_before": history_before,
        "paid_call_performed": False,
    }
    write_json(output, report)
    try:
        result = analyze_bilibili(
            f"https://www.bilibili.com/video/{args.bvid}/",
            settings=settings,
            instruction=args.instruction,
            save_video=False,
        )
        diagnostics = dict(result.get("kimi_diagnostics") or {})
        usage, estimate = _usage_cost(dict(diagnostics.get("usage") or {}))
        report.update(
            {
                "status": "completed" if estimate <= args.approved_budget_cny else "completed_over_budget",
                "finished_at": _now(),
                "history_after": _history_count(settings, args.identity),
                "paid_call_performed": _integer(diagnostics.get("kimi_attempts")) > 0,
                "provider_attempts": _integer(diagnostics.get("kimi_attempts")),
                "finish_reason": str(diagnostics.get("finish_reason") or ""),
                "usage": usage,
                "estimated_cost_cny": estimate,
                "price_basis": {
                    "input_cny_per_million": INPUT_PRICE_CNY_PER_MILLION,
                    "output_cny_per_million": OUTPUT_PRICE_CNY_PER_MILLION,
                    "cache_assumption": "all_prompt_tokens_cache_miss",
                },
                "saved_to": str(result.get("saved_to") or ""),
                "manifest_path": str(result.get("manifest_path") or ""),
                "note_bytes": _integer(result.get("note_bytes")),
                "duration": (result.get("metadata") or {}).get("duration"),
                "source_bytes": _integer(result.get("downloaded_video_bytes")),
                "archived_video": bool(result.get("archived_video")),
                "cached": bool(result.get("cached")),
            }
        )
        write_json(output, report)
        print(output)
        return 0 if report["status"] == "completed" else 3
    except AppError as exc:
        attempts = _integer(exc.details.get("kimi_attempts"))
        report.update(
            {
                "status": "failed",
                "finished_at": _now(),
                "history_after": _history_count(settings, args.identity),
                "paid_call_performed": attempts > 0 or exc.code.startswith("kimi_"),
                "provider_attempts": attempts,
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
    except Exception as exc:
        report.update(
            {
                "status": "failed",
                "finished_at": _now(),
                "history_after": _history_count(settings, args.identity),
                "paid_call_performed": None,
                "error_code": f"internal_{type(exc).__name__}",
                "retryable": False,
            }
        )
        write_json(output, report)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
