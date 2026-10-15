import pytest

from worldguard.campaign.runner import CampaignRunner


@pytest.fixture
def campaign(tmp_path):
    runner = CampaignRunner(tmp_path)
    run = runner.create_campaign("dual_route_stale")
    return runner, run["run_id"]


@pytest.mark.parametrize("invalid", ["../x", "C:\\secret", "https://evil", "", "fake"])
def test_reject_run_ids(campaign, invalid):
    runner, _ = campaign
    with pytest.raises(ValueError):
        runner.list_candidates(invalid)


def test_session_isolation_and_no_arbitrary_config(campaign, tmp_path):
    runner, rid = campaign
    with pytest.raises(ValueError, match="CONFIG_NOT_APPROVED"):
        runner.create_campaign("../../config")
    other = CampaignRunner(tmp_path)
    with pytest.raises(ValueError, match="WRONG_SESSION"):
        other.list_candidates(rid)
    with pytest.raises(ValueError, match="UNKNOWN_CASE"):
        runner.run_case(rid, "invented", "r")
    assert all(set(c) == {"case_id", "fault", "severity"} for c in runner.list_candidates(rid))


def test_recovery_needs_audit_and_does_not_auto_audit(campaign):
    runner, rid = campaign
    p = runner.run_case(rid, "block_route_1", "r")
    assert not runner.runs[rid]["audits"]
    with pytest.raises(ValueError, match="AUDIT_EVIDENCE"):
        runner.recover_case(rid, "block_route_1", "REFRESH_MAP_REPLAN", [p["evidence_id"]], "rec")
    a = runner.audit_path(rid, "block_route_1", p["path_id"])
    assert a["audit"]["status"] == "FAIL"
    rec = runner.recover_case(rid, "block_route_1", "REFRESH_MAP_REPLAN", [a["evidence_id"]], "rec")
    assert rec["path_id"] not in runner.runs[rid]["audits"]
    a2 = runner.audit_path(rid, "block_route_1", rec["path_id"])
    assert a2["audit"]["status"] == "PASS"
    report = runner.finish_campaign(rid)
    assert report["reached_count"] == 1 and report["verdict"] == "FAILURES_FOUND"
    assert report["results"][0]["original_audit"]["status"] == "FAIL"


def test_forbidden_recovery(campaign):
    runner, rid = campaign
    with pytest.raises(ValueError, match="ACTION_NOT_ALLOWED"):
        runner.recover_case(rid, "normal", "SHRINK_ROBOT", [], "r")
