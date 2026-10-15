"""Intake preserves provenance and evaluates the submitted strategy, never uploaded code."""
import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from worldguard.api import create_app
from worldguard.evidence import replay_case
from worldguard.planners.strategy_astar import StrategyAStar

STRATEGY = {"schema_version": "worldguard-strategy/v1", "planner": "strategy_astar",
            "turn_cost_m": 0.7, "clearance_weight": 0.0}


def test_uploaded_strategy_is_used_for_original_and_recovery(tmp_path, monkeypatch):
    monkeypatch.delenv("WORLDGUARD_LIVE_CONFIG", raising=False)
    calls = []
    original = StrategyAStar.plan

    def observed(self, *args, **kwargs):
        calls.append(self.strategy)
        return original(self, *args, **kwargs)
    monkeypatch.setattr(StrategyAStar, "plan", observed)
    app = create_app(tmp_path)
    with TestClient(app) as client:
        response = client.post("/api/v1/submissions", json={"filename": "my_strategy.json", "content": json.dumps(STRATEGY)})
        assert response.status_code == 200
        submission = response.json()
        plan = client.post("/api/v1/missions/plan", json={"config_id": "dual_route_stale",
            "max_cases": 2, "submission_id": submission["submission_id"]}).json()
        created = client.post("/api/v1/runs", json={"config_id": plan["config_id"],
            "mission_id": plan["mission_id"], "request_id": "strategy-test"})
        assert created.status_code == 201, created.text
        rid = created.json()["state"]["run_id"]
        app.state.service.jobs[rid].result(timeout=30)
        report = client.get(f"/api/v1/runs/{rid}/report").json()
        assert report["status"] == "COMPLETED"
        assert len(calls) == 3 and all(s.turn_cost_m == 0.7 for s in calls)
        assert report["results"][1]["original_audit"]["status"] == "FAIL"
        assert report["results"][1]["recovery_audit"]["status"] == "PASS"
        assert all(r["original_plan"]["planner_name"] == "strategy_astar" for r in report["results"])
        assert all(r["navigation_strategy"] == STRATEGY for r in report["results"])
        assert "strategy_astar" in client.get(f"/api/v1/runs/{rid}/report.md").text
        with zipfile.ZipFile(io.BytesIO(client.get(f"/api/v1/runs/{rid}/export").content)) as bundle:
            assert json.loads(bundle.read("submission.json")) == submission
            assert json.loads(bundle.read("mission.json"))["navigation_strategy"] == STRATEGY
        for case in report["results"]:
            replay = replay_case(tmp_path / rid / "cases" / case["case_id"],
                                 tmp_path / ("replay-" + case["case_id"]))
            assert replay["matches"]
            assert replay["model_requests"] == 0
    with TestClient(create_app(tmp_path)) as client:
        assert client.get(f"/api/v1/runs/{rid}").json()["submission"] == submission


def test_python_is_static_only_and_cannot_be_substituted_with_builtin(tmp_path, monkeypatch):
    monkeypatch.delenv("WORLDGUARD_LIVE_CONFIG", raising=False)
    marker = tmp_path / "must-not-run"
    content = f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\ndef plan(scene, task):\n    return []\n"
    with TestClient(create_app(tmp_path)) as client:
        submission = client.post("/api/v1/submissions", json={"filename": "navigator.py", "content": content}).json()
        assert submission["status"] == "STATIC_ONLY"
        assert not marker.exists()
        response = client.post("/api/v1/missions/plan", json={"submission_id": submission["submission_id"]})
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "SUBMISSION_STATIC_ONLY"
        path = tmp_path / "submissions" / (submission["submission_id"] + ".json")
        changed = {**submission, "status": "READY"}
        path.write_text(json.dumps(changed), encoding="utf-8")
        assert client.post("/api/v1/missions/plan", json={"submission_id": submission["submission_id"]}).json()["error"]["code"] == "SUBMISSION_CHANGED"


@pytest.mark.parametrize("payload", [
    {"filename": "../escape.json", "content": json.dumps(STRATEGY)},
    {"filename": "x.json", "content": json.dumps({**STRATEGY, "turn_cost_m": True})},
    {"filename": "x.json", "content": json.dumps({**STRATEGY, "clearance_weight": -1})},
    {"filename": "x.json", "content": json.dumps({**STRATEGY, "clearance_weight": float("nan")})},
    {"filename": "x.json", "content": json.dumps({**STRATEGY, "command": "echo test"})},
    {"filename": "x.py", "content": "#" + "测" * 22000},
])
def test_submission_rejects_invalid_files(tmp_path, monkeypatch, payload):
    monkeypatch.delenv("WORLDGUARD_LIVE_CONFIG", raising=False)
    with TestClient(create_app(tmp_path)) as client:
        assert client.post("/api/v1/submissions", json=payload).status_code in {409, 422}
