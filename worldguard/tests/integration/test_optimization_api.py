import io
import zipfile

from fastapi.testclient import TestClient

from worldguard.api import create_app


def test_optimization_persists_and_exports_without_overwriting_campaign(tmp_path, monkeypatch):
    monkeypatch.delenv("WORLDGUARD_LIVE_CONFIG", raising=False)
    with TestClient(create_app(tmp_path)) as client:
        run = client.post("/api/v1/runs", json={"config_id": "dual_route_stale",
                          "request_id": "opt_fixture", "execution_mode": "manual"}).json()
        base = "/api/v1/runs/" + run["state"]["run_id"]
        case = base + "/cases/block_route_1"
        before = client.get(base).json()
        assert client.get(case + "/optimization").status_code == 404
        response = client.post(case + "/optimize")
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["decision"] == "IMPROVED"
        assert result["model_requests"] == 0
        assert result["planner_evaluations"] == 4
        assert client.post(case + "/optimize").json() == result
        assert client.get(base).json()["state"]["sut_executions"] == before["state"]["sut_executions"]
        assert client.get(case).json()["paths"] == []
        client.post(base + "/finish")
        report = client.get(base + "/report").json()
        with zipfile.ZipFile(io.BytesIO(client.get(base + "/export").content)) as archive:
            assert "optimization/block_route_1.json" in archive.namelist()
    with TestClient(create_app(tmp_path)) as client:
        assert client.get(case + "/optimization").json() == result
        assert client.get(base + "/report").json() == report
