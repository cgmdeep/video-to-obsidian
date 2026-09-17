"""Obsidian source-note contract shared by platform pipelines."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any


def _yaml(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _published(value: str) -> str:
    raw = (value or "").strip()
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    return raw


def build_source_note(
    metadata: dict[str, Any],
    *,
    body: str,
    topic_tags: list[str] | tuple[str, ...],
    transcript: str,
    mode: str,
    archive_status: str,
    archived_video: str = "",
    candidate: bool = False,
) -> str:
    platform = str(metadata.get("platform") or "")
    identity = str(metadata.get("identity") or "")
    title = str(metadata.get("title") or "未命名视频")
    source_uid = (
        f"bilibili:{metadata.get('bvid', '')}:p{int(metadata.get('part') or 1):02d}"
        if platform == "bilibili"
        else f"douyin:{identity}"
    )
    native_tags = [str(item) for item in metadata.get("tags", []) if str(item).strip()]
    process_tags = ["type/source", "status/candidate", f"platform/{platform}"]
    transcript_status = "complete" if transcript.strip() else "disabled"
    fields: list[tuple[str, Any]] = [
        ("schema", "kb-source/v1"),
        ("kind", "source"),
        ("source_uid", source_uid),
        ("status", "candidate"),
        ("title", title),
        ("author", str(metadata.get("uploader") or "")),
        ("published", _published(str(metadata.get("upload_date") or ""))),
        ("source", "哔哩哔哩" if platform == "bilibili" else "抖音"),
        ("platform", platform),
        ("identity", identity),
        ("url", str(metadata.get("url") or "")),
        ("duration", float(metadata.get("duration") or 0)),
        ("ingested", datetime.now().astimezone().strftime("%Y-%m-%d")),
        ("mode", mode),
        ("native_tags", native_tags),
        ("topic_tags", list(topic_tags)),
        ("tags", process_tags),
        ("derived_notes", []),
        ("transcript_status", transcript_status),
        ("archive_status", archive_status),
        ("archived_video", archived_video),
        ("candidate_output", candidate),
        ("body_sha256", hashlib.sha256(body.encode("utf-8")).hexdigest()),
        ("generated_by", "video-to-obsidian"),
    ]
    if platform == "bilibili":
        fields[8:8] = [
            ("bvid", str(metadata.get("bvid") or "")),
            ("part", int(metadata.get("part") or 1)),
        ]
    frontmatter = ["---", *(f"{key}: {_yaml(value)}" for key, value in fields), "---"]
    sections = [
        *frontmatter,
        "",
        f"# {title}",
        "",
        "## 正文",
        "",
        body.strip(),
    ]
    if transcript.strip():
        sections.extend(["", "## 逐字稿", "", "```text", transcript.strip(), "```"])
    return "\n".join(sections).rstrip() + "\n"

