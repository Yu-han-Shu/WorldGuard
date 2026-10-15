import pytest

from worldguard.evidence import replay_case, run_case
from worldguard.faults import CaseSpec
from worldguard.scene import make_scene


def test_recovery_and_replay(tmp_path):
    scene, task = make_scene()
    spec = CaseSpec("block", scene.content_hash, "BLOCK_ROUTE", 11)
    result, case_dir = run_case(scene, task, spec, tmp_path / "runs")
    assert result["original_audit"]["status"] == "FAIL"
    assert result["recovery_audit"]["status"] == "PASS"
    assert result["navigation_status"] == "REACHED"
    assert result["verdict"] == "FAILURES_FOUND"
    assert replay_case(case_dir, tmp_path / "replay")["matches"]
    with pytest.raises(ValueError, match="INSIDE_SOURCE"):
        replay_case(case_dir, case_dir / "replay")
    (case_dir / "plan.json").write_text("{}")
    with pytest.raises(ValueError, match="HASH_MISMATCH"):
        replay_case(case_dir, tmp_path / "tampered")


def test_safe_stop_is_not_reached(tmp_path):
    scene, task = make_scene("single_entry")
    result, _ = run_case(scene, task, CaseSpec("stop", scene.content_hash, "DISCONNECT_GOAL", 11), tmp_path)
    assert result["navigation_status"] == "SAFE_STOP" and not result["reached"]
    assert result["oracle"]["status"] == "UNREACHABLE"
