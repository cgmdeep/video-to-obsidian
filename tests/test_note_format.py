from video_to_obsidian.note_format import build_source_note


def test_source_note_has_searchable_title_and_contract() -> None:
    note = build_source_note(
        {
            "platform": "bilibili",
            "identity": "bilibili_BV1Uw826pE7J_p01",
            "bvid": "BV1Uw826pE7J",
            "part": 1,
            "title": "【巫师】测试",
            "uploader": "巫师财经",
            "upload_date": "20260917",
            "url": "https://www.bilibili.com/video/BV1Uw826pE7J",
            "duration": 60,
            "tags": ["财经"],
        },
        body="### 内容速览\n正文",
        topic_tags=["人物"],
        transcript="原始逐字稿",
        mode="vision",
        archive_status="not_requested",
    )
    assert "# 【巫师】测试" in note
    assert "source_uid: \"bilibili:BV1Uw826pE7J:p01\"" in note
    assert "tags: [\"type/source\", \"status/candidate\", \"platform/bilibili\"]" in note
    assert "derived_notes: []" in note
    assert "## 逐字稿" in note

