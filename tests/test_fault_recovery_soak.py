import importlib.util
from pathlib import Path


def _load_soak_module():
    path = Path(__file__).parents[1] / "scripts" / "run-fault-recovery-soak.py"
    spec = importlib.util.spec_from_file_location("fault_recovery_soak", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fault_recovery_soak_is_offline_and_cleans_media(tmp_path: Path) -> None:
    module = _load_soak_module()
    output = tmp_path / "report.json"

    report = module._run(3, output)

    assert output.is_file()
    assert report["status"] == "completed"
    assert report["iterations_completed"] == 3
    assert report["external_network_used"] is False
    assert report["paid_call_performed"] is False
    assert report["downloads_total"] == 3
    assert report["simulated_kimi_attempts_total"] == 6
    assert report["temporary_media_files_after_each_recovery"] == 0
    assert report["max_working_set_bytes"] >= report["memory_before_bytes"]
    assert report["max_working_set_bytes"] >= report["memory_after_bytes"]
    assert all(sample["cached_repeat"] is True for sample in report["samples"])
