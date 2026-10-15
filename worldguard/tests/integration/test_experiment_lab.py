import io
import zipfile
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from worldguard.api import create_app
from worldguard.contracts import digest
from worldguard.experiment_lab import experiment, passport, probe_passport, run_experiment


def fixture_run(client, config="dual_route_stale"):
    run = client.post("/api/v1/runs", json={"config_id": config, "request_id": "lab_fixture",
                       "execution_mode": "manual"}).json()
    base = "/api/v1/runs/" + run["state"]["run_id"]
    case = base + "/cases/block_route_1"
    path = client.post(case + "/run", json={"request_id": "plan"}).json()
    audit = client.post(case + "/audit", json={"path_id": path["path_id"]}).json()
    recovery = client.post(case + "/recover", json={"action": "REFRESH_MAP_REPLAN",
                           "evidence_ids": [audit["evidence_id"]], "request_id": "recovery"}).json()
    client.post(case + "/audit", json={"path_id": recovery["path_id"]})
    return base, case, run["state"]["run_id"]


def test_counterfactual_controls_persistence_and_original_evidence(tmp_path, monkeypatch):
    monkeypatch.delenv("WORLDGUARD_LIVE_CONFIG", raising=False)
    with TestClient(create_app(tmp_path)) as client:
        base, url, _rid = fixture_run(client)
        assert client.post(url + "/experiment").status_code == 409
        client.post(base + "/finish")
        frozen = client.get(url).json()
        report = client.get(base + "/report").json()
        response = client.post(url + "/experiment")
        assert response.status_code == 200, response.text
        result = response.json()
        a, b, c = result["branches"]
        assert [x["outcome"] for x in (a, b, c)] == ["REJECTED", "PASS", "PASS"]
        assert len({x["audit"]["binding"]["environment_hash"] for x in (a, b, c)}) == 1
        assert len({x["audit"]["binding"]["constraints_hash"] for x in (a, b, c)}) == 1
        assert a["plan"]["planner_scene_hash"] != b["plan"]["planner_scene_hash"]
        assert a["plan"]["planner_name"] == b["plan"]["planner_name"]
        assert "planner_implementation" in c["changes"]
        assert result["planner_evaluations"] == 2 and result["model_requests"] == 0
        assert result["experiment_hash"] == digest({k: v for k, v in result.items() if k != "experiment_hash"})
        assert client.post(url + "/experiment").json() == result
        assert client.get(url).json() == frozen
        assert client.get(base + "/report").json() == report
        from worldguard.evidence_chat import context
        snapshot, citations = context(client.app.state.service, _rid, "block_route_1")
        assert snapshot["counterfactual_experiments"][0]["experiment_hash"] == result["experiment_hash"]
        assert result["source_evidence_id"] in citations
        with zipfile.ZipFile(io.BytesIO(client.get(base + "/export").content)) as archive:
            assert "experiments/block_route_1.json" in archive.namelist()
    with TestClient(create_app(tmp_path)) as client:
        assert client.get(url + "/experiment").json() == result
        assert client.post(url + "/experiment").json() == result
        assert client.get(base + "/report").json() == report


def test_passport_invalidates_copies_without_changing_case(tmp_path, monkeypatch):
    monkeypatch.delenv("WORLDGUARD_LIVE_CONFIG", raising=False)
    with TestClient(create_app(tmp_path)) as client:
        _, url, _ = fixture_run(client)
        frozen = client.get(url).json()
        valid = client.get(url + "/passport").json()
        assert valid["valid"] and valid["geometry_status"] == "PASS"
        assert valid["passport_hash"] == digest({k: v for k, v in valid.items() if k != "passport_hash"})
        for change, fields in [("map", ["environment_hash"]), ("robot", ["task_hash", "constraints_hash"])]:
            result = client.post(url + "/passport/probe", json={"path_id": valid["path_id"], "change": change})
            assert result.status_code == 200, result.text
            data = result.json()
            assert data["binding_status"] == "STALE_CERTIFICATE"
            assert data["changed_fields"] == fields
            if change == "map":
                assert data["audit"]["status"] == "FAIL"
            assert client.get(url).json() == frozen
            assert client.get(url + "/passport").json() == valid
        failed_id = frozen["paths"][0]["path_id"]
        failed = client.get(url + "/passport", params={"path_id": failed_id}).json()
        assert failed["valid"] is False and failed["certificate_hash"] is None
        assert client.post(url + "/passport/probe", json={"path_id": failed_id, "change": "map"}).status_code == 409
        assert client.post(url + "/passport/probe", json={"path_id": valid["path_id"], "change": "erase"}).status_code == 422
        assert client.get(url + "/passport", params={"path_id": "other_run_path"}).status_code == 404


def test_inconclusive_branches_not_pass_and_tampered_passport_rejected(tmp_path, monkeypatch):
    monkeypatch.delenv("WORLDGUARD_LIVE_CONFIG", raising=False)
    from worldguard.contracts import PlanResult
    with TestClient(create_app(tmp_path)) as client:
        _, url, _ = fixture_run(client)
        case = client.get(url).json()
        def timeout(self, scene, task, **kwargs):
            return PlanResult(self.name, "test", scene.content_hash, (), "PLANNER_TIMEOUT", 10, None)
        monkeypatch.setattr("worldguard.experiment_lab.ReferenceAStar.plan", timeout)
        monkeypatch.setattr("worldguard.experiment_lab.StrategyAStar.plan", timeout)
        result = run_experiment(case, {})
        assert [b["outcome"] for b in result["branches"]][1:] == ["INCONCLUSIVE", "INCONCLUSIVE"]
        assert all(b["score"] is None for b in result["branches"])
        case["paths"][-1]["audit"]["audit"]["binding"]["environment_hash"] = "changed"
        assert not passport(case)["valid"]
        with pytest.raises(ValueError, match="PASSPORT_NOT_VALID"):
            probe_passport(case, case["paths"][-1]["path_id"], "map")


def test_double_click_runs_once(tmp_path, monkeypatch):
    monkeypatch.delenv("WORLDGUARD_LIVE_CONFIG", raising=False)
    with TestClient(create_app(tmp_path)) as client:
        base, _, rid = fixture_run(client)
        client.post(base + "/finish")
        calls = []
        original = run_experiment
        def counted(*args):
            calls.append(1)
            return original(*args)
        monkeypatch.setattr("worldguard.experiment_lab.run_experiment", counted)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(experiment, client.app.state.service, rid, "block_route_1", create=True) for _ in range(2)]
            assert futures[0].result() == futures[1].result()
        assert len(calls) == 1


def test_json_strategy_controls_preserved_and_no_false_repair(tmp_path, monkeypatch):
    monkeypatch.delenv("WORLDGUARD_LIVE_CONFIG", raising=False)
    with TestClient(create_app(tmp_path)) as client:
        run = client.post("/api/v1/runs", json={"config_id": "dual_route_current", "request_id": "strategy",
                           "execution_mode": "manual"}).json()
        rid = run["state"]["run_id"]
        owner = client.app.state.service.runner._get(rid)
        owner["config"]["navigation_strategy"] = {"turn_cost_m": 0.8, "clearance_weight": 0.5}
        owner["config"]["submission_id"] = "test_strategy"
        url = f"/api/v1/runs/{rid}/cases/block_route_1"
        plan = client.post(url + "/run", json={"request_id": "plan"}).json()
        client.post(url + "/audit", json={"path_id": plan["path_id"]})
        client.post(f"/api/v1/runs/{rid}/finish")
        result = client.post(url + "/experiment").json()
        a, b, c = result["branches"]
        assert a["parameters"] == b["parameters"] == owner["config"]["navigation_strategy"]
        assert c["parameters"]["turn_cost_m"] == 0.8
        assert b["changes"] == []
        assert c["changes"] == ["strategy_parameters"]
        assert a["outcome"] == "PASS"
        assert "原始路径已通过" in result["conclusion"]
