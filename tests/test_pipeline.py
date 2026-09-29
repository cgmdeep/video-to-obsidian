from dataclasses import replace
import json
from pathlib import Path

import pytest

from video_to_obsidian.config import AppPaths, TranscriptSettings, initialize_settings, load_settings
from video_to_obsidian.errors import AppError
from video_to_obsidian.kimi import KimiResult
from video_to_obsidian.media import PreparedVideo
from video_to_obsidian.pipeline import (
    BilibiliDependencies,
    SingleVideoDependencies,
    analyze_bilibili,
    analyze_douyin,
)
from video_to_obsidian.platforms.bilibili import BilibiliMetadata, ResolvedBilibili
from video_to_obsidian.platforms.douyin import DouyinMetadata, ResolvedDouyin
from video_to_obsidian.preferences import write_preferences
from video_to_obsidian.transcript import TranscriptResult


def _settings(tmp_path: Path, *, transcript: bool = False):
    config = initialize_settings(
        tmp_path / "vault",
        config_path=tmp_path / "config.toml",
        runtime_root=tmp_path / "private",
    )
    settings = load_settings(config)
    paths = AppPaths(
        config_file=config,
        cache=tmp_path / "runtime/cache",
        state=tmp_path / "runtime/state",
        candidates=tmp_path / "runtime/candidates",
        archive=tmp_path / "runtime/archive",
    )
    return replace(
        settings,
        paths=paths,
        profile="transcript" if transcript else "standard",
        transcript=TranscriptSettings("remote" if transcript else "off", False),
    )


def _metadata() -> BilibiliMetadata:
    return BilibiliMetadata(
        identity="bilibili_BV1Uw826pE7J_p01",
        bvid="BV1Uw826pE7J",
        part=1,
        url="https://www.bilibili.com/video/BV1Uw826pE7J",
        title="【巫师】测试视频",
        uploader="巫师财经",
        uploader_id="1",
        duration=120,
        upload_date="20260917",
        description="描述",
        tags=("财经",),
        yt_dlp_id="BV1Uw826pE7J",
        download_auth="firefox_profile",
    )


class FakePipeline:
    def __init__(self, *, kimi_error: AppError | None = None, transcript_error: AppError | None = None):
        self.kimi_calls = 0
        self.transcript_calls = 0
        self.download_calls = 0
        self.last_instruction = ""
        self.kimi_error = kimi_error
        self.transcript_error = transcript_error

    def deps(self) -> BilibiliDependencies:
        def download(resolved, metadata, output, settings):
            self.download_calls += 1
            path = output / "source.mp4"
            path.write_bytes(b"video-data")
            return path

        def kimi(video, metadata, mode, instruction, is_proxy):
            self.kimi_calls += 1
            self.last_instruction = instruction
            if self.kimi_error:
                raise self.kimi_error
            return KimiResult(
                "### 内容速览\n" + "完整视频笔记。" * 20,
                ("财经", "人物"),
                (),
                {
                    "kimi_attempts": 1,
                    "finish_reason": "stop",
                    "usage": {"prompt_tokens": 100, "completion_tokens": 200},
                    "content_chars": 140,
                    "reasoning_chars": 20,
                    "refusal_chars": 0,
                },
            )

        def transcript(video, settings):
            self.transcript_calls += 1
            if self.transcript_error:
                raise self.transcript_error
            return TranscriptResult("逐字稿", 1024)

        return BilibiliDependencies(
            resolve=lambda text: ResolvedBilibili(
                "BV1Uw826pE7J",
                None,
                "https://www.bilibili.com/video/BV1Uw826pE7J",
                "bvid",
            ),
            metadata=lambda resolved, settings: _metadata(),
            download=download,
            probe=lambda path: {"has_video": True, "has_audio": True, "size_bytes": path.stat().st_size},
            prepare=lambda video, duration, checkpoint, settings: PreparedVideo(video, False),
            kimi=kimi,
            transcript=transcript,
        )


def test_standard_pipeline_writes_readable_note_and_skips_asr(tmp_path: Path) -> None:
    fake = FakePipeline()
    settings = _settings(tmp_path)
    result = analyze_bilibili(
        "BV1Uw826pE7J",
        settings=settings,
        dependencies=fake.deps(),
    )
    assert result["ok"] is True
    assert result["saved_to"].endswith(
        "【巫师】测试视频 bilibili_BV1Uw826pE7J_p01.md"
    )
    assert fake.kimi_calls == 1
    assert fake.transcript_calls == 0
    assert result["source_checkpoint_exists"] is False
    note = Path(result["saved_to"]).read_text(encoding="utf-8")
    assert "platform/bilibili" in note
    assert "derived_notes: []" in note
    assert "## 逐字稿" not in note
    history = Path(result["kimi_history_path"])
    assert history.is_file()
    history_text = history.read_text(encoding="utf-8")
    assert "completed" in history_text
    assert "完整视频笔记" not in history_text


def test_completed_request_is_cached_without_second_kimi_call(tmp_path: Path) -> None:
    fake = FakePipeline()
    settings = _settings(tmp_path)
    first = analyze_bilibili("BV1Uw826pE7J", settings=settings, dependencies=fake.deps())
    second = analyze_bilibili("BV1Uw826pE7J", settings=settings, dependencies=fake.deps())
    assert first["cached"] is False
    assert second["cached"] is True
    assert fake.kimi_calls == 1
    assert fake.download_calls == 1


def test_long_term_and_one_time_preferences_reach_kimi(tmp_path: Path) -> None:
    fake = FakePipeline()
    settings = _settings(tmp_path)
    write_preferences(settings, "长期更详细，保留数据和反讽语境")
    result = analyze_bilibili(
        "BV1Uw826pE7J",
        settings=settings,
        instruction="本次重点看图表",
        dependencies=fake.deps(),
    )
    assert "长期更详细，保留数据和反讽语境" in fake.last_instruction
    assert "本次重点看图表" in fake.last_instruction
    assert result["preferences_applied"] is True
    assert result["preference_chars"] > 0


def test_kimi_failure_preserves_source_checkpoint(tmp_path: Path) -> None:
    fake = FakePipeline(
        kimi_error=AppError(
            "kimi_output_budget_exhausted",
            "预算耗尽",
            details={
                "kimi_attempts": 1,
                "finish_reason": "length",
                "usage": {"completion_tokens": 16384},
            },
        )
    )
    settings = _settings(tmp_path)
    with pytest.raises(AppError) as caught:
        analyze_bilibili("BV1Uw826pE7J", settings=settings, dependencies=fake.deps())
    assert caught.value.code == "kimi_output_budget_exhausted"
    assert caught.value.retryable is False
    assert caught.value.details["source_checkpoint_exists"] is True
    assert fake.kimi_calls == 1
    history = list((settings.paths.state / "history").rglob("*.json"))
    assert len(history) == 1
    record = json.loads(history[0].read_text(encoding="utf-8"))
    assert record["outcome"] == "failed"
    assert record["error_code"] == "kimi_output_budget_exhausted"
    assert record["diagnostics"]["usage"]["completion_tokens"] == 16384


def test_manual_retry_after_kimi_failure_reuses_download_checkpoint(tmp_path: Path) -> None:
    fake = FakePipeline(
        kimi_error=AppError(
            "kimi_connection_failed",
            "Kimi 连接中断",
            retryable=True,
            details={"kimi_attempts": 1},
        )
    )
    settings = _settings(tmp_path)

    with pytest.raises(AppError, match="Kimi 连接中断"):
        analyze_bilibili("BV1Uw826pE7J", settings=settings, dependencies=fake.deps())

    fake.kimi_error = None
    result = analyze_bilibili("BV1Uw826pE7J", settings=settings, dependencies=fake.deps())

    assert result["ok"] is True
    assert fake.download_calls == 1
    assert fake.kimi_calls == 2
    assert result["source_checkpoint_exists"] is False
    history = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (settings.paths.state / "history").rglob("*.json")
    ]
    assert sorted(item["outcome"] for item in history) == ["completed", "failed"]


def test_runtime_artifacts_are_outside_vault(tmp_path: Path) -> None:
    fake = FakePipeline()
    settings = _settings(tmp_path)
    result = analyze_bilibili("BV1Uw826pE7J", settings=settings, dependencies=fake.deps())

    vault = settings.vault_path.resolve()
    assert Path(result["saved_to"]).is_relative_to(vault)
    for runtime_path in (
        settings.paths.cache,
        settings.paths.state,
        settings.paths.candidates,
        settings.paths.archive,
    ):
        assert not runtime_path.resolve().is_relative_to(vault)
    assert not any(
        path.name in {"cache", "state", "candidates", "archive"}
        for path in vault.iterdir()
    )


def test_metadata_failure_leaves_secret_free_submission_receipt(tmp_path: Path) -> None:
    fake = FakePipeline()
    dependencies = fake.deps()
    dependencies = replace(
        dependencies,
        metadata=lambda resolved, settings: (_ for _ in ()).throw(
            AppError(
                "command_timeout",
                "yt-dlp 执行超时",
                retryable=True,
                details={"phase": "yt-dlp", "timeout_seconds": 120},
            )
        ),
    )
    settings = _settings(tmp_path)
    with pytest.raises(AppError):
        analyze_bilibili("BV1Uw826pE7J", settings=settings, dependencies=dependencies)

    receipts = list((settings.paths.state / "submissions").glob("*.json"))
    assert len(receipts) == 1
    receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
    assert receipt["status"] == "failed"
    assert receipt["stage"] == "yt-dlp"
    assert receipt["paid_call_performed"] is False
    assert "BV1Uw826pE7J" not in receipts[0].read_text(encoding="utf-8")


def test_optional_transcript_failure_does_not_block_note(tmp_path: Path) -> None:
    fake = FakePipeline(transcript_error=AppError("asr_failed", "ASR暂时不可用", retryable=True))
    settings = _settings(tmp_path, transcript=True)
    result = analyze_bilibili("BV1Uw826pE7J", settings=settings, dependencies=fake.deps())
    assert result["ok"] is True
    assert fake.transcript_calls == 1
    assert "ASR暂时不可用" in result["degradations"]


def test_deep_analysis_becomes_candidate_when_formal_note_exists(tmp_path: Path) -> None:
    fake = FakePipeline()
    settings = _settings(tmp_path)
    formal = analyze_bilibili("BV1Uw826pE7J", settings=settings, dependencies=fake.deps())
    deep = analyze_bilibili(
        "BV1Uw826pE7J",
        settings=settings,
        mode="deep",
        dependencies=fake.deps(),
    )
    assert Path(formal["saved_to"]).is_file()
    assert not deep["saved_to"]
    assert Path(deep["candidate_saved_to"]).is_file()
    assert settings.paths.candidates in Path(deep["candidate_saved_to"]).parents


def test_existing_legacy_note_blocks_before_download_or_kimi(tmp_path: Path) -> None:
    fake = FakePipeline()
    settings = _settings(tmp_path)
    legacy = settings.vault_path / "旧版笔记.md"
    legacy.write_text(
        "---\n"
        'identity: "bilibili_BV1Uw826pE7J_p01"\n'
        'generated_by: "video-to-obsidian"\n'
        "---\n\n旧正文\n",
        encoding="utf-8",
    )

    with pytest.raises(AppError) as caught:
        analyze_bilibili("BV1Uw826pE7J", settings=settings, dependencies=fake.deps())

    assert caught.value.code == "existing_note_conflict"
    assert fake.download_calls == 0
    assert fake.kimi_calls == 0


def test_changed_preferences_create_candidate_instead_of_overwriting_formal_note(
    tmp_path: Path,
) -> None:
    fake = FakePipeline()
    settings = _settings(tmp_path)
    formal = analyze_bilibili("BV1Uw826pE7J", settings=settings, dependencies=fake.deps())
    formal_content = Path(formal["saved_to"]).read_text(encoding="utf-8")
    write_preferences(settings, "以后严格按时间线展开")

    revised = analyze_bilibili("BV1Uw826pE7J", settings=settings, dependencies=fake.deps())

    assert revised["output_kind"] == "candidate"
    assert not revised["saved_to"]
    assert Path(revised["candidate_saved_to"]).is_file()
    assert Path(formal["saved_to"]).read_text(encoding="utf-8") == formal_content
    assert fake.kimi_calls == 2


def test_douyin_uses_same_safe_pipeline(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    calls = {"kimi": 0, "transcript": 0}

    def download(resolved, metadata, output, cfg):
        path = output / "source.mp4"
        path.write_bytes(b"douyin-video")
        return path

    def kimi(video, metadata, mode, instruction, is_proxy):
        calls["kimi"] += 1
        return KimiResult(
            "### 内容速览\n" + "抖音正式笔记。" * 20,
            ("短视频",),
            (),
            {"kimi_attempts": 1, "finish_reason": "stop", "usage": {}},
        )

    deps = SingleVideoDependencies(
        resolve=lambda text: ResolvedDouyin("https://v.douyin.com/abc123/", "short_url"),
        metadata=lambda resolved, cfg: DouyinMetadata(
            identity="douyin_1234567890123456789",
            aweme_id="1234567890123456789",
            url=resolved.url,
            title="测试抖音标题",
            uploader="作者",
            uploader_id="1",
            duration=30,
            upload_date="20260917",
            description="",
            tags=("知识",),
            download_auth="firefox_profile",
        ),
        download=download,
        probe=lambda path: {"has_video": True, "has_audio": True},
        prepare=lambda video, duration, checkpoint, cfg: PreparedVideo(video, False),
        kimi=kimi,
        transcript=lambda video, cfg: (_ for _ in ()).throw(AssertionError("standard must skip ASR")),
    )
    result = analyze_douyin(
        "https://v.douyin.com/abc123/",
        settings=settings,
        dependencies=deps,
    )
    assert result["platform"] == "douyin"
    assert result["saved_to"].endswith("测试抖音标题 douyin_1234567890123456789.md")
    assert calls["kimi"] == 1
    note = Path(result["saved_to"]).read_text(encoding="utf-8")
    assert "platform/douyin" in note
