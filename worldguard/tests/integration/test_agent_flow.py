"""MOCK orchestration tests; these are not evidence of actual model behavior."""

import random

from worldguard.campaign.baselines import execute, select_case
from worldguard.campaign.runner import CampaignRunner
from worldguard.evidence import replay_case


def test_offline_shared_core_flow(tmp_path):
    runner = CampaignRunner(tmp_path / "runs")
    rid = runner.create_campaign("single_entry_stale")["run_id"]
    report = execute(runner, rid)
    assert report["runtime_mode"] == "DETERMINISTIC"
    assert report["reached_count"] == 1 and report["safe_stop_count"] == 1
    assert report["model_requests"] == 0
    assert report["status"] == "COMPLETED"
    case_dir = tmp_path / "runs" / rid / "cases" / "disconnect_goal_1"
    assert replay_case(case_dir, tmp_path / "replay")["matches"]


def test_feedback_changes_adaptive_boundary_choice():
    candidates = [{"case_id": str(i), "fault": "PINCH_CLEARANCE", "severity": i} for i in (1, 3, 4)]
    tried = {"fault": "PINCH_CLEARANCE", "severity": 2}
    failed = select_case("AdaptiveRule", candidates, [(tried, "FAIL")], random.Random(1))
    passed = select_case("AdaptiveRule", candidates, [(tried, "PASS")], random.Random(1))
    assert failed["severity"] > passed["severity"]
