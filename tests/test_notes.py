from pathlib import Path

import pytest

from video_to_obsidian.notes import NoteWriteError, note_filename, write_note


def test_human_readable_filename() -> None:
    assert note_filename("【巫师】赵薇的资本博弈", "bilibili_BV1LiypBAEAQ_p01") == (
        "【巫师】赵薇的资本博弈 bilibili_BV1LiypBAEAQ_p01.md"
    )


def test_atomic_note_write_and_no_overwrite(tmp_path: Path) -> None:
    target = write_note(
        tmp_path,
        platform="bilibili",
        title="测试/标题",
        identity="bilibili_BV123_p01",
        content="# 正文",
    )
    assert target.name == "测试 标题 bilibili_BV123_p01.md"
    assert target.read_text(encoding="utf-8") == "# 正文\n"
    with pytest.raises(NoteWriteError):
        write_note(
            tmp_path,
            platform="bilibili",
            title="测试/标题",
            identity="bilibili_BV123_p01",
            content="# 新正文",
        )


def test_rejects_empty_note(tmp_path: Path) -> None:
    with pytest.raises(NoteWriteError):
        write_note(tmp_path, platform="douyin", title="x", identity="y", content="  ")

