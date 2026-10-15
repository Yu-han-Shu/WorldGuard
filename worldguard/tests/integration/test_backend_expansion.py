"""Expanded synthetic maps and bounded agent optimization; no external model calls."""

import io
import json
import threading
import urllib.request
import zipfile
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from worldguard.api import create_app
from worldguard.api_models import CreateRun
from worldguard.api_service import ApiService
from worldguard.campaign.runner import CampaignRunner
from worldguard.contracts import digest
from worldguard.evidence import read_json
from worldguard.exports import export_run
from worldguard.faults import CaseSpec, inject
from worldguard.live_mcp import BoundMcp
from worldguard.optimization import optimize
from worldguard.planners.reference_astar import ReferenceAStar
from worldguard.scene import COMPLEX_FAMILIES, DEV_SEEDS, FAULT_KINDS, complex_layout, make_scene
from worldguard.verifier.audit import audit_path


@pytest.mark.parametrize("family", COMPLEX_FAMILIES)
@pytest.mark.parametrize("seed", DEV_SEEDS)
def test_complex_maps_have_reproducible_distinct_geometry_and_real_faults(family, seed):
    scene, task = make_scene(family, seed)
    assert len({make_scene(family, s)[0].occupied for s in DEV_SEEDS}) == 3
    assert scene == make_scene(family, seed)[0]
    original = ReferenceAStar().plan(scene, task)
    assert audit_path(scene, task, original.path)["status"] == "PASS"
    previous = scene.content_hash, task.task_hash, task.robot.constraints_hash
    for severity in range(1, len(complex_layout(family, seed)[-1]) + 1):
        fault = CaseSpec(f"fault_{severity}", scene.content_hash, FAULT_KINDS[family], seed, severity)
        after = inject(scene, fault)
        assert inject(scene, fault) == after
        assert set(scene.occupied) < set(after.occupied)
        assert audit_path(after, task, original.path)["status"] == "FAIL"
        recovery = ReferenceAStar().plan(after, task)
        if FAULT_KINDS[family] == "DISCONNECT_GOAL":
            assert recovery.code == "NO_PATH"
        else:
            assert audit_path(after, task, recovery.path)["status"] == "PASS"
        assert previous == (scene.content_hash, task.task_hash, task.robot.constraints_hash)
    altered = replace(scene, occupied=(*scene.occupied, (0, 0)))
    with pytest.raises(ValueError, match="FAULT_REGION_UNSUPPORTED"):
        inject(altered, CaseSpec("bad", altered.content_hash, "NONE", seed))


def test_catalog_and_automatic_office_flow(tmp_path, monkeypatch):
    monkeypatch.delenv("WORLDGUARD_LIVE_CONFIG", raising=False)
    app = create_app(tmp_path)
    with TestClient(app) as client:
        catalog = client.get("/api/v1/configs").json()["items"]
        assert len(catalog) == 72
        assert len({(c["family"], c["seed"]) for c in catalog}) == 36
        assert len({c["family"] for c in catalog}) == 14
        for entry in catalog:
            scene, _ = make_scene(entry["family"], entry["seed"])
            assert (entry["width_cells"], entry["height_cells"]) == (scene.width, scene.height)
        assert all(c["description"] for c in catalog)
        created = client.post("/api/v1/runs", json={"config_id": "office_s23_stale",
                              "request_id": "office_fixture"})
        assert created.status_code == 201, created.text
        rid = created.json()["state"]["run_id"]
        app.state.service.jobs[rid].result(timeout=15)
        base = f"/api/v1/runs/{rid}"
        report = client.get(base + "/report").json()
        assert report["reached_count"] == report["planned_cases"] == 4
        assert sum(r["original_audit"]["status"] == "FAIL" for r in report["results"]) == 3
        case = base + "/cases/block_route_3"
        result = client.post(case + "/optimize").json()
        assert result["decision"] == "IMPROVED"
        assert result["metric_changes"]["turns"] < 0
        assert client.get(case + "/map.svg").status_code == 200
        with zipfile.ZipFile(io.BytesIO(client.get(base + "/export").content)) as archive:
            assert json.loads(archive.read("optimization/block_route_3.json"))["scene_hash"] == result["scene_hash"]


def audited(runner, rid, cid):
    plan = runner.run_case(rid, cid, "plan_" + cid)
    return runner.audit_path(rid, cid, plan["path_id"])["evidence_id"]


def test_optimization_budgets_idempotency_evidence_and_cancellation(tmp_path):
    runner = CampaignRunner(tmp_path)
    rid = runner.create_campaign("office_stale")["run_id"]
    with pytest.raises(ValueError, match="AUDIT_EVIDENCE_REQUIRED"):
        runner.optimize_case(rid, "normal", "invented", "invalid")
    normal = audited(runner, rid, "normal")
    fault = audited(runner, rid, "block_route_1")
    with pytest.raises(ValueError, match="AUDIT_EVIDENCE_REQUIRED"):
        runner.optimize_case(rid, "block_route_1", normal, "wrong_case")
    first = runner.optimize_case(rid, "normal", normal, "opt_1")
    assert runner.optimize_case(rid, "normal", normal, "opt_1") == first
    with pytest.raises(ValueError, match="REQUEST_ID_CONFLICT"):
        runner.optimize_case(rid, "block_route_1", fault, "opt_1")
    second = runner.optimize_case(rid, "block_route_1", fault, "opt_2")
    assert second["applied_to_navigation"] is False
    assert second["decision"] == "IMPROVED"
    run = runner._get(rid)
    assert run["optimization_evaluations"] == 8 and run["actions"] == 2
    assert len(run["plans"]) == 2 and len(run["optimizations"]) == 2
    assert runner.optimize_case(rid, "normal", normal, "cache") == first
    third = audited(runner, rid, "block_route_2")
    with pytest.raises(ValueError, match="OPTIMIZATION_BUDGET_EXHAUSTED"):
        runner.optimize_case(rid, "block_route_2", third, "opt_3")
    report = runner.finish_campaign(rid)
    assert report["optimizations"] == [first, second]
    assert report["results"][1]["original_audit"]["status"] == "FAIL"
    assert report["reached_count"] == 1  # Optimization never fabricates arrival.
    with zipfile.ZipFile(io.BytesIO(export_run(tmp_path, rid))) as archive:
        full = json.loads(archive.read("evidence/" + second["evidence_id"] + ".json"))
        assert full == json.loads(archive.read("optimization/block_route_1.json"))
        assert full["constraints_hash"] == run["task"].robot.constraints_hash
    cancelled = runner.create_campaign("warehouse_stale")["run_id"]
    eid = audited(runner, cancelled, "normal")
    runner.stop_campaign(cancelled)
    with pytest.raises(ValueError, match="CAMPAIGN_NOT_RUNNING"):
        runner.optimize_case(cancelled, "normal", eid, "cancelled")


def test_deadline_does_not_turn_partial_search_into_no_safe_path(tmp_path, monkeypatch):
    scene, task = make_scene("warehouse")
    with pytest.raises(ValueError, match="OPTIMIZATION_TIMEOUT"):
        optimize(scene, task, timeout=0)
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(ValueError, match="OPTIMIZATION_CANCELLED"):
        optimize(scene, task, cancel=cancel)
    runner = CampaignRunner(tmp_path)
    rid = runner.create_campaign("warehouse_stale")["run_id"]
    eid = audited(runner, rid, "normal")

    def timeout(*args, **kwargs):
        raise ValueError("OPTIMIZATION_TIMEOUT")

    monkeypatch.setattr("worldguard.campaign.runner.optimize", timeout)
    with pytest.raises(ValueError, match="OPTIMIZATION_TIMEOUT"):
        runner.optimize_case(rid, "normal", eid, "timeout")
    assert read_json(tmp_path / rid / "state.json")["optimization_evaluations"] == 4
    assert not (tmp_path / rid / "optimization").exists()


def test_real_bound_mcp_optimization_transport_and_event_hashes(tmp_path):
    service = ApiService(tmp_path)
    rid = service.create(CreateRun(config_id="warehouse_stale", request_id="mcp_fixture",
                                  execution_mode="manual"))["state"]["run_id"]
    eid = audited(service.runner, rid, "block_route_1")
    try:
        with BoundMcp(service, rid, "fixture-token") as mcp:
            def call(args):
                request = urllib.request.Request(mcp.url, data=json.dumps({"jsonrpc": "2.0", "id": 1,
                    "method": "tools/call", "params": {"name": "wg_optimize_case", "arguments": args}}).encode(),
                    headers={"Authorization": "Bearer fixture-token", "Content-Type": "application/json",
                             "Accept": "application/json, text/event-stream"})
                with urllib.request.urlopen(request, timeout=15) as response:
                    return json.load(response)["result"]
            args = {"run_id": rid, "case_id": "block_route_1", "evidence_id": eid, "request_id": "opt"}
            assert call({**args, "run_id": "other"})["isError"]
            result = call(args)
            assert not result.get("isError")
            output = result.get("structuredContent") or json.loads(result["content"][0]["text"])
            assert output["decision"] == "IMPROVED"
            event = service.runner._get(rid)["events"][-1]
            assert event["tool_name"] == "wg_optimize_case"
            assert event["input_hash"] == digest({"case_id": "block_route_1", "evidence_id": eid})
            assert event["output_hash"] == digest(output)
            mcp.finish_requested = True
            refused = call({**args, "request_id": "after_finish"})
            payload = refused.get("structuredContent") or json.loads(refused["content"][0]["text"])
            assert payload["error_code"] == "CAMPAIGN_FINISH_REQUESTED"
    finally:
        service.close()
