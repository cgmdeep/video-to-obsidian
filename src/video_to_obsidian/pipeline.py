"""Checkpointed single-video pipelines."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .config import Settings
from .errors import AppError
from .kimi import KimiResult, KimiVideoClient
from .media import KIMI_FILE_LIMIT_BYTES, PreparedVideo, hash_file, prepare_kimi_video, probe_video
from .note_format import build_source_note
from .notes import (
    NoteWriteError,
    find_note_by_identity,
    safe_identity,
    safe_title,
    write_candidate,
    write_note,
)
from .platforms.bilibili import download_video, fetch_metadata, resolve_input
from .platforms.douyin import (
    download_video as download_douyin_video,
    fetch_metadata as fetch_douyin_metadata,
    resolve_input as resolve_douyin_input,
)
from .state import read_json, write_json
from .transcript import TranscriptResult, transcribe_video


@dataclass(frozen=True)
class SingleVideoDependencies:
    resolve: Callable[[str], Any]
    metadata: Callable[[Any, Settings], Any]
    download: Callable[[Any, Any, Path, Settings], Path]
    probe: Callable[[Path], dict[str, Any]]
    prepare: Callable[[Path, float, Path, Settings], PreparedVideo]
    kimi: Callable[[Path, dict[str, Any], str, str, bool], KimiResult]
    transcript: Callable[[Path, Settings], TranscriptResult]


BilibiliDependencies = SingleVideoDependencies


def default_bilibili_dependencies(settings: Settings) -> SingleVideoDependencies:
    client = KimiVideoClient(settings)
    return SingleVideoDependencies(
        resolve=resolve_input,
        metadata=lambda resolved, cfg: fetch_metadata(resolved, cfg),
        download=lambda resolved, metadata, output, cfg: download_video(
            resolved, metadata, output, cfg
        ),
        probe=probe_video,
        prepare=lambda video, duration, checkpoint, cfg: prepare_kimi_video(
            video,
            duration_seconds=duration,
            checkpoint_dir=checkpoint,
            settings=cfg,
        ),
        kimi=lambda video, metadata, mode, instruction, is_proxy: client.analyze(
            video,
            metadata,
            mode=mode,
            instruction=instruction,
            is_proxy=is_proxy,
        ),
        transcript=lambda video, cfg: transcribe_video(video, cfg),
    )


def default_douyin_dependencies(settings: Settings) -> SingleVideoDependencies:
    client = KimiVideoClient(settings)
    return SingleVideoDependencies(
        resolve=resolve_douyin_input,
        metadata=lambda resolved, cfg: fetch_douyin_metadata(resolved, cfg),
        download=lambda resolved, metadata, output, cfg: download_douyin_video(
            resolved, metadata, output, cfg
        ),
        probe=probe_video,
        prepare=lambda video, duration, checkpoint, cfg: prepare_kimi_video(
            video,
            duration_seconds=duration,
            checkpoint_dir=checkpoint,
            settings=cfg,
        ),
        kimi=lambda video, metadata, mode, instruction, is_proxy: client.analyze(
            video,
            metadata,
            mode=mode,
            instruction=instruction,
            is_proxy=is_proxy,
        ),
        transcript=lambda video, cfg: transcribe_video(video, cfg),
    )


def _fingerprint(mode: str, instruction: str, settings: Settings) -> str:
    payload = {
        "pipeline": "video-to-obsidian/v0.1",
        "mode": mode,
        "instruction": instruction.strip(),
        "model": settings.deep_model if mode == "deep" else settings.default_model,
        "max_tokens": settings.deep_max_tokens if mode == "deep" else settings.vision_max_tokens,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _checkpoint_source(manifest: dict[str, Any]) -> Path | None:
    raw = str(manifest.get("source_path") or "")
    if not raw:
        return None
    path = Path(raw)
    if not path.is_file() or path.stat().st_size <= 0:
        return None
    expected_size = int(manifest.get("source_bytes") or 0)
    if expected_size and path.stat().st_size != expected_size:
        return None
    expected_hash = str(manifest.get("source_sha256") or "")
    if expected_hash and hash_file(path) != expected_hash:
        return None
    return path


def _archive_source(
    source: Path,
    metadata: dict[str, Any],
    settings: Settings,
    source_hash: str,
) -> Path:
    settings.paths.archive.mkdir(parents=True, exist_ok=True)
    date = str(metadata.get("upload_date") or "")
    date_suffix = f"_{date[:4]}-{date[4:6]}-{date[6:]}" if len(date) == 8 and date.isdigit() else ""
    suffix = source.suffix.lower() or ".mp4"
    filename = (
        f"{safe_title(str(metadata.get('title') or '未命名视频'))} "
        f"{safe_identity(str(metadata.get('identity') or 'video'))}{date_suffix}{suffix}"
    )
    target = settings.paths.archive / filename
    if target.is_file():
        if target.stat().st_size == source.stat().st_size and hash_file(target) == source_hash:
            return target
        raise AppError("archive_conflict", "归档目录已有同名但内容不同的视频，已停止覆盖。")
    temporary = target.parent / f".{target.name}.{os.getpid()}.tmp"
    try:
        shutil.copy2(source, temporary)
        if temporary.stat().st_size != source.stat().st_size or hash_file(temporary) != source_hash:
            raise AppError("archive_verify_failed", "归档复制完成后校验失败。")
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def _summary(body: str) -> str:
    return body.strip()[:1200]


def _result(manifest: dict[str, Any], *, cached: bool) -> dict[str, Any]:
    saved_to = str(manifest.get("saved_to") or "")
    candidate = str(manifest.get("candidate_saved_to") or "")
    if saved_to and not Path(saved_to).is_file():
        saved_to = ""
    if candidate and not Path(candidate).is_file():
        candidate = ""
    note_path = Path(candidate or saved_to) if (candidate or saved_to) else None
    archived = str(manifest.get("archived_video") or "")
    if archived and not Path(archived).is_file():
        archived = ""
    result: dict[str, Any] = {
        "ok": bool(note_path),
        "complete": manifest.get("status") == "completed" and bool(note_path),
        "status": manifest.get("status", "unknown"),
        "platform": manifest.get("platform", ""),
        "mode": manifest.get("mode", "vision"),
        "model": manifest.get("model", ""),
        "cached": cached,
        "identity": manifest.get("identity", ""),
        "metadata": manifest.get("metadata") or {},
        "summary": _summary(str(manifest.get("note_body") or "")),
        "saved_to": saved_to,
        "candidate_saved_to": candidate,
        "output_kind": "candidate" if candidate else "formal_note",
        "archive_status": manifest.get("archive_status", "not_requested"),
        "degradations": manifest.get("degradations") or [],
        "manifest_path": manifest.get("manifest_path", ""),
        "downloaded_video_bytes": int(manifest.get("source_bytes") or 0),
        "kimi_proxy_bytes": int(manifest.get("kimi_proxy_bytes") or 0),
        "transcript_audio_bytes": int(manifest.get("transcript_audio_bytes") or 0),
        "transcript_chars": len(str(manifest.get("transcript") or "")),
        "note_bytes": note_path.stat().st_size if note_path else 0,
        "kimi_diagnostics": manifest.get("kimi_diagnostics") or {},
        "usage": (manifest.get("kimi_diagnostics") or {}).get("usage") or {},
        "source_checkpoint_exists": _checkpoint_source(manifest) is not None,
        "checkpoint_reusable": _checkpoint_source(manifest) is not None,
    }
    if archived:
        result["archived_video"] = archived
    final_delta = result["note_bytes"] + (Path(archived).stat().st_size if archived else 0)
    result["final_disk_delta_bytes"] = final_delta
    return result


def _analyze_single_video(
    share_text: str,
    *,
    platform: str,
    settings: Settings,
    mode: str = "vision",
    instruction: str = "",
    save_video: bool | None = None,
    dependencies: SingleVideoDependencies,
) -> dict[str, Any]:
    mode = (mode or "vision").strip().lower()
    if mode not in {"vision", "deep"}:
        raise AppError("unsupported_mode", "视频分析只支持 vision 或 deep 档位。")
    keep_video = settings.save_video if save_video is None else bool(save_video)
    deps = dependencies
    resolved = deps.resolve(share_text)
    metadata_object = deps.metadata(resolved, settings)
    metadata = metadata_object.to_dict()
    identity = metadata_object.identity
    state_dir = settings.paths.state / platform
    manifest_path = state_dir / (f"{identity}.deep.json" if mode == "deep" else f"{identity}.json")
    prior = read_json(manifest_path)
    request_fingerprint = _fingerprint(mode, instruction, settings)

    output_key = "candidate_saved_to" if prior.get("candidate_output") else "saved_to"
    existing_output = str(prior.get(output_key) or "")
    if (
        prior.get("status") == "completed"
        and prior.get("request_fingerprint") == request_fingerprint
        and existing_output
        and Path(existing_output).is_file()
    ):
        return _result(prior, cached=True)

    same_request = prior.get("request_fingerprint") == request_fingerprint
    manifest: dict[str, Any] = dict(prior) if same_request else {}
    if not same_request and prior:
        for key in (
            "source_path",
            "source_bytes",
            "source_sha256",
            "probe",
            "transcript",
            "transcript_audio_bytes",
            "archived_video",
            "archive_status",
            "kimi_proxy_path",
            "kimi_proxy_bytes",
            "kimi_proxy_source_sha256",
        ):
            if key in prior:
                manifest[key] = prior[key]
    formal_note = find_note_by_identity(settings.vault_path, platform, identity)
    candidate_output = mode == "deep" and formal_note is not None
    manifest.update(
        {
            "schema_version": 1,
            "identity": identity,
            "platform": platform,
            "metadata": metadata,
            "mode": mode,
            "model": settings.deep_model if mode == "deep" else settings.default_model,
            "request_fingerprint": request_fingerprint,
            "candidate_output": candidate_output,
            "status": "running",
            "stage": manifest.get("stage", "metadata"),
            "archive_status": manifest.get("archive_status", "pending" if keep_video else "not_requested"),
            "degradations": list(manifest.get("degradations") or []),
            "manifest_path": str(manifest_path),
            "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
    )
    manifest.pop("error", None)
    write_json(manifest_path, manifest)

    try:
        checkpoint_dir = settings.paths.cache / "checkpoints" / identity
        source = _checkpoint_source(manifest)
        if source is None:
            checkpoint_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=f"{identity}-download-") as temporary:
                downloaded = deps.download(resolved, metadata_object, Path(temporary), settings)
                probe = deps.probe(downloaded)
                source_hash = hash_file(downloaded)
                source_bytes = downloaded.stat().st_size
                suffix = downloaded.suffix.lower() or ".mp4"
                source = checkpoint_dir / f"source{suffix}"
                temporary_source = checkpoint_dir / f".source{suffix}.tmp"
                shutil.copy2(downloaded, temporary_source)
                if temporary_source.stat().st_size != source_bytes or hash_file(temporary_source) != source_hash:
                    raise AppError("checkpoint_verify_failed", "下载检查点复制后校验失败。")
                os.replace(temporary_source, source)
            manifest.update(
                {
                    "stage": "source_checkpointed",
                    "source_path": str(source),
                    "source_bytes": source_bytes,
                    "source_sha256": source_hash,
                    "probe": probe,
                }
            )
            write_json(manifest_path, manifest)
        else:
            source_hash = str(manifest.get("source_sha256") or hash_file(source))
            source_bytes = source.stat().st_size

        if keep_video:
            archived = str(manifest.get("archived_video") or "")
            if not archived or not Path(archived).is_file():
                archive_path = _archive_source(source, metadata, settings, source_hash)
                manifest["archived_video"] = str(archive_path)
            manifest["archive_status"] = "saved"
        else:
            manifest["archive_status"] = "not_requested"
            manifest.pop("archived_video", None)
        manifest["stage"] = "archive_checkpointed"
        write_json(manifest_path, manifest)

        transcript = str(manifest.get("transcript") or "")
        if settings.transcript.mode != "off" and not transcript:
            try:
                transcript_result = deps.transcript(source, settings)
                transcript = transcript_result.text
                manifest["transcript"] = transcript
                manifest["transcript_audio_bytes"] = transcript_result.audio_bytes
            except AppError as exc:
                if settings.transcript.required:
                    raise
                manifest["degradations"] = list(
                    dict.fromkeys((manifest.get("degradations") or []) + [exc.message])
                )
                manifest["transcript_audio_bytes"] = 0
        else:
            manifest.setdefault("transcript_audio_bytes", 0)
        manifest["stage"] = "transcript_complete" if transcript else "transcript_disabled"
        write_json(manifest_path, manifest)

        proxy_path = Path(str(manifest.get("kimi_proxy_path") or ""))
        if not (
            proxy_path.is_file()
            and proxy_path.stat().st_size > 0
            and proxy_path.stat().st_size <= KIMI_FILE_LIMIT_BYTES
            and manifest.get("kimi_proxy_source_sha256") == source_hash
        ):
            prepared = deps.prepare(source, metadata_object.duration, checkpoint_dir, settings)
            proxy_path = prepared.path
            manifest["kimi_proxy_path"] = str(proxy_path) if prepared.is_proxy else ""
            manifest["kimi_proxy_bytes"] = proxy_path.stat().st_size if prepared.is_proxy else 0
            manifest["kimi_proxy_source_sha256"] = source_hash
            manifest["degradations"] = list(
                dict.fromkeys((manifest.get("degradations") or []) + list(prepared.warnings))
            )
        else:
            prepared = PreparedVideo(
                proxy_path,
                True,
                ("复用此前生成的完整时间线低码率分析代理。",),
            )
        manifest["stage"] = "kimi_input_ready"
        write_json(manifest_path, manifest)

        body = str(manifest.get("note_body") or "") if same_request else ""
        if len(body) >= 80:
            kimi_result = KimiResult(
                body,
                tuple(manifest.get("topic_tags") or []),
                (),
                dict(manifest.get("kimi_diagnostics") or {}),
            )
        else:
            kimi_result = deps.kimi(
                prepared.path,
                metadata,
                mode,
                instruction,
                prepared.is_proxy,
            )
            manifest.update(
                {
                    "stage": "vision_complete",
                    "note_body": kimi_result.body,
                    "topic_tags": list(kimi_result.topic_tags),
                    "kimi_diagnostics": kimi_result.diagnostics,
                    "degradations": list(
                        dict.fromkeys(
                            (manifest.get("degradations") or []) + list(kimi_result.warnings)
                        )
                    ),
                }
            )
            write_json(manifest_path, manifest)

        note = build_source_note(
            metadata,
            body=kimi_result.body,
            topic_tags=kimi_result.topic_tags,
            transcript=transcript,
            mode=mode,
            archive_status=str(manifest.get("archive_status") or "not_requested"),
            archived_video=str(manifest.get("archived_video") or ""),
            candidate=candidate_output,
        )
        try:
            if candidate_output:
                marker = f"deep-{request_fingerprint[:10]}"
                saved = write_candidate(
                    settings.paths.candidates / platform,
                    title=metadata_object.title,
                    identity=identity,
                    content=note,
                    marker=marker,
                )
                manifest["candidate_saved_to"] = str(saved)
                manifest.pop("saved_to", None)
            else:
                if formal_note is not None:
                    raise AppError(
                        "existing_note_conflict",
                        "Vault 中已存在相同稳定身份的正式笔记，拒绝覆盖。",
                    )
                saved = write_note(
                    settings.vault_path,
                    platform=platform,
                    title=metadata_object.title,
                    identity=identity,
                    content=note,
                )
                manifest["saved_to"] = str(saved)
                manifest.pop("candidate_saved_to", None)
        except NoteWriteError as exc:
            raise AppError("note_save_failed", str(exc)) from exc
        manifest["stage"] = "note_saved"
        write_json(manifest_path, manifest)

        if manifest.get("kimi_proxy_path"):
            Path(str(manifest["kimi_proxy_path"])).unlink(missing_ok=True)
            manifest["kimi_proxy_path"] = ""
        if not keep_video:
            source.unlink(missing_ok=True)
            manifest["source_path"] = ""
        manifest["stage"] = "finished"
        manifest["status"] = "completed"
        manifest["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        write_json(manifest_path, manifest)
        return _result(manifest, cached=False)
    except AppError as exc:
        manifest.update(
            {
                "status": "failed",
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                },
                "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            }
        )
        if exc.code.startswith("kimi_"):
            manifest["kimi_diagnostics"] = exc.details
        write_json(manifest_path, manifest)
        details = dict(exc.details)
        details.update(
            {
                "manifest_path": str(manifest_path),
                "checkpoint_stage": str(manifest.get("stage") or ""),
                "source_checkpoint_exists": _checkpoint_source(manifest) is not None,
                "checkpoint_reusable": _checkpoint_source(manifest) is not None,
                "transcript_chars": len(str(manifest.get("transcript") or "")),
                "kimi_proxy_exists": bool(
                    manifest.get("kimi_proxy_path")
                    and Path(str(manifest.get("kimi_proxy_path"))).is_file()
                ),
                "archive_status": str(manifest.get("archive_status") or "not_requested"),
            }
        )
        if manifest.get("archived_video") and Path(str(manifest["archived_video"])).is_file():
            details["archived_video"] = str(manifest["archived_video"])
        raise AppError(
            exc.code,
            exc.message,
            retryable=exc.retryable,
            details=details,
        ) from exc


def analyze_bilibili(
    share_text: str,
    *,
    settings: Settings,
    mode: str = "vision",
    instruction: str = "",
    save_video: bool | None = None,
    dependencies: SingleVideoDependencies | None = None,
) -> dict[str, Any]:
    return _analyze_single_video(
        share_text,
        platform="bilibili",
        settings=settings,
        mode=mode,
        instruction=instruction,
        save_video=save_video,
        dependencies=dependencies or default_bilibili_dependencies(settings),
    )


def analyze_douyin(
    share_text: str,
    *,
    settings: Settings,
    mode: str = "vision",
    instruction: str = "",
    save_video: bool | None = None,
    dependencies: SingleVideoDependencies | None = None,
) -> dict[str, Any]:
    return _analyze_single_video(
        share_text,
        platform="douyin",
        settings=settings,
        mode=mode,
        instruction=instruction,
        save_video=save_video,
        dependencies=dependencies or default_douyin_dependencies(settings),
    )
