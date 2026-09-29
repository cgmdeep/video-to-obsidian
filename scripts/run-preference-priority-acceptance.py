"""Verify one-time instructions override conflicting private preferences."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

from video_to_obsidian.config import load_settings
from video_to_obsidian.errors import AppError
from video_to_obsidian.notes import find_note_by_identity
from video_to_obsidian.pipeline import analyze_bilibili
from video_to_obsidian.state import read_json, write_json


INPUT_PRICE_CNY_PER_MILLION = 6.50
OUTPUT_PRICE_CNY_PER_MILLION = 27.00
LONG_TERM_PREFERENCE = (
    "每条视频只写一段、不超过120个字；不要使用标题，不要保留任何数字或参数。"
)
ONE_TIME_INSTRUCTION = (
    "本次必须以多级标题写成不少于500字的结构化长笔记，并忠实保留视频中"
    "出现的数字、百分比、刷新率、分辨率和其他参数。"
)


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


def _history_count(settings: Any, identity: str) -> int:
    directory = settings.paths.state / "history" / "bilibili" / identity
    return len(list(directory.glob("*.json"))) if directory.is_dir() else 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("bvid")
    parser.add_argument("--identity", required=True)
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

    base = load_settings(args.config)
    if base.default_model != "kimi-k2.7-code":
        raise SystemExit("preference acceptance requires kimi-k2.7-code")
    manifest_path = base.paths.state / "bilibili" / f"{args.identity}.json"
    prior = read_json(manifest_path)
    formal = find_note_by_identity(base.vault_path, "bilibili", args.identity)
    if prior.get("status") != "completed" or formal is None:
        raise SystemExit("a completed formal note is required before preference acceptance")
    formal_hash_before = _sha256(formal)
    history_before = _history_count(base, args.identity)

    output = args.output or base.paths.state / "acceptance" / "quality-preference-priority-k27.json"
    lock = output.with_suffix(output.suffix + ".started")
    preference_file = base.paths.state / "acceptance" / ".quality-preference-priority.txt"
    if output.exists() or lock.exists() or preference_file.exists():
        raise SystemExit("this acceptance has already started")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise SystemExit("this acceptance has already started") from exc
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"started_at": _now(), "call_index": args.call_index}, handle)
        handle.write("\n")
    preference_file.write_text(LONG_TERM_PREFERENCE + "\n", encoding="utf-8", newline="\n")
    settings = replace(base, preferences_file=preference_file)

    report: dict[str, Any] = {
        "schema_version": 1,
        "kind": "preference_priority_acceptance",
        "identity": args.identity,
        "started_at": _now(),
        "status": "running",
        "model": settings.default_model,
        "call_index": args.call_index,
        "approved_max_calls": args.approved_max_calls,
        "remaining_approved_budget_cny": args.approved_budget_cny,
        "history_before": history_before,
        "formal_note": str(formal),
        "formal_sha256_before": formal_hash_before,
        "long_term_rule": "one_paragraph_under_120_chars_without_numbers_or_headings",
        "one_time_rule": "structured_over_500_chars_with_numbers_and_headings",
        "paid_call_performed": False,
    }
    write_json(output, report)
    try:
        result = analyze_bilibili(
            f"https://www.bilibili.com/video/{args.bvid}/",
            settings=settings,
            instruction=ONE_TIME_INSTRUCTION,
            save_video=False,
        )
        diagnostics = dict(result.get("kimi_diagnostics") or {})
        usage, estimate = _usage_cost(dict(diagnostics.get("usage") or {}))
        candidate = Path(str(result.get("candidate_saved_to") or ""))
        candidate_text = candidate.read_text(encoding="utf-8") if candidate.is_file() else ""
        body = candidate_text.split("\n## 正文\n", 1)[-1]
        formal_hash_after = _sha256(formal)
        checks = {
            "output_is_candidate": result.get("output_kind") == "candidate" and candidate.is_file(),
            "candidate_outside_vault": candidate.is_file()
            and base.vault_path.expanduser().resolve() not in candidate.resolve().parents,
            "formal_note_unchanged": formal_hash_after == formal_hash_before,
            "one_time_length_won": len(body) >= 500,
            "one_time_headings_won": body.count("\n### ") >= 2,
            "one_time_numbers_won": any(character.isdigit() for character in body),
            "preferences_applied": bool(result.get("preferences_applied")),
        }
        report.update(
            {
                "status": "completed" if all(checks.values()) and estimate <= args.approved_budget_cny else "completed_failed_acceptance",
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
                "candidate_saved_to": str(candidate),
                "candidate_bytes": candidate.stat().st_size if candidate.is_file() else 0,
                "body_chars": len(body),
                "formal_sha256_after": formal_hash_after,
                "checks": checks,
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
                "formal_sha256_after": _sha256(formal),
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
                "formal_sha256_after": _sha256(formal),
            }
        )
        write_json(output, report)
        return 1
    finally:
        preference_file.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
