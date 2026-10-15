import pytest

from worldguard.campaign.runner import CampaignRunner


def test_retry_conflict_cancel(tmp_path):
    runner = CampaignRunner(tmp_path)
    rid = runner.create_campaign("dual_route_stale")["run_id"]
    first = runner.run_case(rid, "normal", "req")
    assert runner.run_case(rid, "normal", "req") == first
    assert runner.runs[rid]["actions"] == 1
    with pytest.raises(ValueError, match="CONFLICT"):
        runner.run_case(rid, "block_route_1", "req")
    runner.stop_campaign(rid)
    assert runner.run_case(rid, "normal", "req") == first
    with pytest.raises(ValueError, match="NOT_RUNNING"):
        runner.run_case(rid, "block_route_1", "new")
    assert runner.finish_campaign(rid)["status"] == "CANCELLED"
