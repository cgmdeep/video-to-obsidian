from dataclasses import replace
from pathlib import Path

import pytest

from video_to_obsidian.config import AppPaths, TranscriptSettings, initialize_settings, load_settings
from video_to_obsidian.errors import AppError
from video_to_obsidian.kimi import KimiResult
from video_to_obsidian.media import PreparedVideo
from video_to_obsidian.pipeline import BilibiliDependencies, analyze_bilibili
from video_to_obsidian.platforms.bilibili import BilibiliMetadata, ResolvedBilibili
from video_to_obsidian.transcript import TranscriptResult


def _settings(tmp_path: Path, *, transcript: bool = False):
    config = initialize_settings(tmp_path / "vault", config_path=tmp_path / "config.toml")
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


def test_completed_request_is_cached_without_second_kimi_call(tmp_path: Path) -> None:
    fake = FakePipeline()
    settings = _settings(tmp_path)
    first = analyze_bilibili("BV1Uw826pE7J", settings=settings, dependencies=fake.deps())
    second = analyze_bilibili("BV1Uw826pE7J", settings=settings, dependencies=fake.deps())
    assert first["cached"] is False
    assert second["cached"] is True
    assert fake.kimi_calls == 1
    assert fake.download_calls == 1


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

