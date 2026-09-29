from pathlib import Path

import pytest

from video_to_obsidian.notes import (
    NoteWriteError,
    find_note_by_identity,
    note_filename,
    write_note,
)


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


def test_find_note_by_identity_discovers_legacy_root_note(tmp_path: Path) -> None:
    legacy = tmp_path / "旧版文件名.md"
    legacy.write_text(
        "---\n"
        'schema: "kb-source/v1"\n'
        'identity: "douyin_7681133341692677414"\n'
        'generated_by: "video-to-obsidian"\n'
        "---\n\n正文\n",
        encoding="utf-8",
    )

    assert find_note_by_identity(
        tmp_path,
        "douyin",
        "douyin_7681133341692677414",
    ) == legacy


def test_find_note_by_identity_ignores_unmanaged_notes(tmp_path: Path) -> None:
    user_note = tmp_path / "我的笔记.md"
    user_note.write_text(
        "---\n"
        'identity: "douyin_7681133341692677414"\n'
        "---\n\n用户自己的笔记\n",
        encoding="utf-8",
    )

    assert find_note_by_identity(
        tmp_path,
        "douyin",
        "douyin_7681133341692677414",
    ) is None


def test_find_note_by_identity_rejects_duplicates_across_layouts(tmp_path: Path) -> None:
    identity = "bilibili_BV12ftJ6rEkw_p01"
    managed = (
        "---\n"
        'source_uid: "bilibili:BV12ftJ6rEkw:p01"\n'
        'generated_by: "video-to-obsidian"\n'
        "---\n\n正文\n"
    )
    (tmp_path / "旧笔记.md").write_text(managed, encoding="utf-8")
    platform_folder = tmp_path / "Bilibili"
    platform_folder.mkdir()
    (platform_folder / f"新笔记 {identity}.md").write_text(managed, encoding="utf-8")

    with pytest.raises(NoteWriteError, match="多个相同稳定身份"):
        find_note_by_identity(tmp_path, "bilibili", identity)


def test_find_note_by_identity_ignores_sync_version_backups(tmp_path: Path) -> None:
    identity = "bilibili_BV1Uw826pE7J_p01"
    managed = (
        "---\n"
        'identity: "bilibili_BV1Uw826pE7J_p01"\n'
        'generated_by: "video-to-obsidian"\n'
        "---\n\n正文\n"
    )
    platform_folder = tmp_path / "Bilibili"
    platform_folder.mkdir()
    active = platform_folder / f"正式笔记 {identity}.md"
    active.write_text(managed, encoding="utf-8")
    versions = tmp_path / "#SyncVersion"
    versions.mkdir()
    (versions / f"历史版本 {identity}.md").write_text(managed, encoding="utf-8")

    assert find_note_by_identity(tmp_path, "bilibili", identity) == active
