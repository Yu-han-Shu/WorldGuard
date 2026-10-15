"""Exercise the frontend's actual HTTP contracts against the shared navigation core."""

import io
import threading
import time
import zipfile

import pytest
from fastapi.testclient import TestClient

from worldguard.api import create_app


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        yield client


def create(client, **values):
    response = client.post(
        "/api/v1/runs",
        json={
            "config_id": "dual_route_stale",
            "request_id": "create_1",
            "execution_mode": "manual",
            **values,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_full_manual_recovery_and_downloads(client):
    run = create(client)
    rid = run["state"]["run_id"]
    base = f"/api/v1/runs/{rid}"
    assert create(client)["state"]["run_id"] == rid
    assert client.get(base + "/report").status_code == 409
    candidates = client.get(base + "/candidates").json()["items"]
    assert [c["case_id"] for c in candidates] == ["normal", "block_route_1"]
    case = base + "/cases/block_route_1"
    before = client.get(case).json()
    assert before["paths"] == []
    assert before["scene_before"]["content_hash"] != before["scene_after"]["content_hash"]
    assert client.get(case + "/map.svg").status_code == 200
    plan = client.post(case + "/run", json={"request_id": "plan_1"}).json()
    assert client.post(case + "/run", json={"request_id": "plan_1"}).json() == plan
    assert plan["audit_status"] == "NOT_RUN"
    audit = client.post(case + "/audit", json={"path_id": plan["path_id"]}).json()
    assert audit["audit"]["status"] == "FAIL"
    assert client.get(base + "/evidence/" + audit["evidence_id"]).json()["audit"]["status"] == "FAIL"
    recovery = client.post(
        case + "/recover",
        json={
            "action": "REFRESH_MAP_REPLAN",
            "evidence_ids": [audit["evidence_id"]],
            "request_id": "recover_1",
        },
    ).json()
    assert recovery["audit_status"] == "NOT_RUN"
    assert (
        client.post(case + "/audit", json={"path_id": recovery["path_id"]}).json()["audit"]["status"]
        == "PASS"
    )
    assert len(client.get(case).json()["paths"]) == 2
    report = client.post(base + "/finish").json()
    assert report["reached_count"] == 1
    assert report["results"][0]["original_audit"]["status"] == "FAIL"
    assert client.get(base + "/report").json() == report
    assert client.get(base + "/report.md").status_code == 200
    svg = client.get(case + "/map.svg")
    assert svg.headers["content-type"].startswith("image/svg+xml") and "polyline" in svg.text
    with zipfile.ZipFile(io.BytesIO(client.get(base + "/export").content)) as archive:
        assert "cases/block_route_1/manifest.json" in archive.namelist()
    first = client.get(base + "/events?limit=2").json()
    assert len(first["items"]) == 2 and first["has_more"]
    second = client.get(base + "/events", params={"cursor": first["next_cursor"]}).json()
    assert not {e["event_id"] for e in first["items"]} & {e["event_id"] for e in second["items"]}
    assert client.get("/api/v1/runs").json()["total"] == 1


def test_automatic_stop_and_historical_read(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        run = create(client, config_id="single_entry_stale", execution_mode="automatic")
        base = f"/api/v1/runs/{run['state']['run_id']}"
        for _ in range(100):
            state = client.get(base).json()
            if not state["job_active"]:
                break
            time.sleep(0.01)
        assert not state["job_active"]
        report = client.get(base + "/report").json()
        assert report["safe_stop_count"] == 1 and report["reached_count"] == 1
    with TestClient(create_app(tmp_path)) as restarted:
        assert restarted.get(base).json()["read_only"]
        assert restarted.get(base + "/cases/disconnect_goal_1").json()["stopped"]
        assert restarted.get(base + "/report").json() == report
        blocked = restarted.post(base + "/cases/normal/run", json={"request_id": "new"})
        assert blocked.status_code == 409
        assert blocked.json()["error"]["code"] == "RUN_READ_ONLY_AFTER_RESTART"


def test_cancel_conflict_invalid_input_and_cors(client):
    run = create(client)
    base = f"/api/v1/runs/{run['state']['run_id']}"
    assert client.post(base + "/stop", json={}).json()["state"]["status"] == "CANCELLED"
    assert client.post(base + "/cases/normal/run", json={"request_id": "x"}).status_code == 409
    conflict = client.post("/api/v1/runs", json={"config_id": "corridor_stale", "request_id": "create_1"})
    assert conflict.json()["error"]["code"] == "REQUEST_ID_CONFLICT"
    invalid = client.post(
        "/api/v1/runs", json={"config_id": "dual_route_stale", "request_id": "x", "goal": [0, 0]}
    )
    assert invalid.status_code == 422
    assert all("input" not in detail for detail in invalid.json()["error"]["details"])
    live = client.post(
        "/api/v1/runs",
        json={"config_id": "dual_route_stale", "request_id": "live", "runtime_mode": "LIVE_AGNES"},
    )
    assert live.status_code == 503 and live.json()["error"]["code"] == "LIVE_NOT_AVAILABLE"
    assert client.get("/api/v1/runs/unknown").status_code == 404
    assert client.get(base + "/events?cursor=-1").status_code == 422
    assert client.get(base + "/cases/unknown").status_code == 404
    cors = client.options(
        "/api/v1/runs", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"}
    )
    assert cors.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert (
        "access-control-allow-origin"
        not in client.get("/api/v1/health", headers={"Origin": "https://unlisted.example"}).headers
    )
    assert client.get("/openapi.json").json()["info"]["version"] == "1.0.0"


def test_queued_automatic_run_can_be_cancelled_without_actions(client, monkeypatch):
    from worldguard import api_service

    entered, release = threading.Event(), threading.Event()
    original = api_service.execute

    def delayed(runner, rid, tester, seed):
        entered.set()
        assert release.wait(5)
        return original(runner, rid, tester, seed)

    monkeypatch.setattr(api_service, "execute", delayed)
    first = create(client, execution_mode="automatic")
    assert entered.wait(2)
    try:
        second = create(client, request_id="create_2", execution_mode="automatic")
        base = f"/api/v1/runs/{second['state']['run_id']}"
        assert client.post(base + "/cases/normal/run", json={"request_id": "manual"}).status_code == 409
        stopped = client.post(base + "/stop", json={}).json()
        assert stopped["state"]["status"] == "CANCELLED"
        assert stopped["state"]["sut_executions"] == 0
        assert not stopped["job_active"]
    finally:
        release.set()
    assert first["state"]["run_id"] != second["state"]["run_id"]


def test_restart_marks_unfinished_run_as_interrupted(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        run = create(client)
    with TestClient(create_app(tmp_path)) as client:
        result = client.get(f"/api/v1/runs/{run['state']['run_id']}").json()
        assert create(client)["state"]["run_id"] == run["state"]["run_id"]
        assert result["interrupted"] and result["read_only"]
        assert result["state"]["status"] == "BLOCKED"
        assert not result["report_available"]


def test_legacy_campaign_is_readable_and_openapi_is_current(tmp_path):
    import json
    from pathlib import Path

    from worldguard.campaign.baselines import execute
    from worldguard.campaign.runner import CampaignRunner

    runner = CampaignRunner(tmp_path)
    rid = runner.create_campaign("dual_route_stale")["run_id"]
    execute(runner, rid)
    with TestClient(create_app(tmp_path)) as client:
        base = f"/api/v1/runs/{rid}"
        assert client.get(base).json()["execution_mode"] == "legacy"
        assert len(client.get(base + "/cases/block_route_1").json()["paths"]) == 2
        assert client.get(base + "/cases/block_route_1/map.svg").status_code == 200
        assert client.get(base + "/export").status_code == 200
        schema = Path(__file__).resolve().parents[2] / "frontend/openapi.json"
        assert client.get("/openapi.json").json() == json.loads(schema.read_text(encoding="utf-8"))
