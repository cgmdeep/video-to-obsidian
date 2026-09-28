from pathlib import Path

import pytest

from video_to_obsidian.errors import AppError
from video_to_obsidian.locking import exclusive_task_lock


def test_second_holder_is_rejected_without_waiting(tmp_path: Path) -> None:
    lock = tmp_path / "task.lock"
    with exclusive_task_lock(lock):
        with pytest.raises(AppError) as caught:
            with exclusive_task_lock(lock):
                raise AssertionError("unreachable")
    assert caught.value.code == "task_in_progress"
    assert caught.value.retryable is False

