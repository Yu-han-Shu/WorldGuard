import pytest

from worldguard.campaign.runner import CampaignRunner


@pytest.mark.parametrize("terminal", ["COMPLETED", "CANCELLED", "BLOCKED", "ERROR"])
def test_terminal_elapsed_is_frozen(tmp_path, monkeypatch, terminal):
    clock = [100.0]
    monkeypatch.setattr("worldguard.campaign.runner.time.monotonic", lambda: clock[0])
    runner = CampaignRunner(tmp_path)
    rid = runner.create_campaign("dual_route_stale")["run_id"]
    run = runner.runs[rid]
    clock[0] = 103.0
    assert runner._public(run)["elapsed_seconds"] == 3.0
    clock[0] = 105.0
    if terminal == "COMPLETED":
        runner.finish_campaign(rid)
    elif terminal == "CANCELLED":
        runner.stop_campaign(rid)
    else:
        run["status"] = terminal
    assert runner._public(run)["elapsed_seconds"] == 5.0
    clock[0] = 1000.0
    assert runner._public(run)["elapsed_seconds"] == 5.0
