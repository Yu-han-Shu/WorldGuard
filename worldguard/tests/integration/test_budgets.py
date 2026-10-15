import pytest

from worldguard.agh_bridge import LiveBlocked, run_live
from worldguard.campaign.runner import CampaignRunner


def test_budget_and_all_reruns_count(tmp_path):
    runner = CampaignRunner(tmp_path)
    rid = runner.create_campaign("dual_route_current")["run_id"]
    runner.run_case(rid, "normal", "first")
    for i in range(11):
        runner.run_case(rid, "normal", f"retry{i}", rerun=True)
    with pytest.raises(ValueError, match="SUT_BUDGET"):
        runner.run_case(rid, "normal", "overflow", rerun=True)
    assert runner.runs[rid]["actions"] == 12


def test_timeout_and_live_guard(tmp_path):
    runner = CampaignRunner(tmp_path)
    rid = runner.create_campaign("dual_route_current")["run_id"]
    runner.runs[rid]["started"] -= 121
    with pytest.raises(ValueError, match="WALL_TIME"):
        runner.run_case(rid, "normal", "first")
    assert runner.runs[rid]["actions"] == 0
    with pytest.raises(LiveBlocked):
        run_live({"external_model_calls_allowed": True})
