"""Offline boundary tests. No official provider is invoked by this test module."""

import io
import json
import threading
import time
import urllib.error
import urllib.request
import zipfile

import pytest
from fastapi.testclient import TestClient

from worldguard.api import create_app
from worldguard.api_models import CreateRun
from worldguard.api_service import ApiService
from worldguard.live_mcp import BoundMcp
from worldguard.live_runtime import PINNED_AGH, LiveRuntime, execution_failure


def test_real_mcp_transport_authentication_session_binding_and_deferred_finish(tmp_path):
    service = ApiService(tmp_path)
    rid = service.create(CreateRun(config_id="dual_route_stale", request_id="offline", execution_mode="manual"))["state"]["run_id"]
    try:
        with BoundMcp(service, rid, "fixture-token") as mcp:
            with pytest.raises(urllib.error.HTTPError) as denied:
                urllib.request.urlopen(mcp.url, timeout=2)
            assert denied.value.code == 401

            def call(name, args):
                payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                           "params": {"name": name, "arguments": args}}
                req = urllib.request.Request(mcp.url, data=json.dumps(payload).encode(), headers={
                    "Authorization": "Bearer fixture-token", "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                })
                with urllib.request.urlopen(req, timeout=5) as response:
                    return json.load(response)["result"]

            assert not call("wg_health", {"nonce": "offline123"}).get("isError")
            assert call("wg_run_case", {"run_id": "other", "case_id": "normal", "request_id": "x"})["isError"]
            assert call("wg_create_campaign", {"config_id": "single_entry_stale"})["isError"]
            assert not call("wg_finish_campaign", {"run_id": rid}).get("isError")
            assert mcp.finish_requested
            assert not (service.folder(rid) / "report.json").exists()
            assert service.runner._get(rid)["actions"] == 0
    finally:
        service.close()


def test_budget_reservation_survives_restart_and_interrupted_child(tmp_path, monkeypatch):
    runtime_root = tmp_path / "agh"
    tsx = runtime_root / "node_modules/tsx/dist/cli.mjs"
    tsx.parent.mkdir(parents=True)
    tsx.write_text("// offline fixture")
    monkeypatch.setattr("subprocess.run", lambda *a, **k: type("Result", (), {"stdout": PINNED_AGH})())
    config = tmp_path / "budget.local.json"
    config.write_text(json.dumps({"external_model_calls_allowed": True, "approval_reference": "OFFLINE_TEST",
                                 "agh_root": str(runtime_root), "credential_home": str(tmp_path),
                                 "max_total_requests": 4, "max_requests_per_run": 3,
                                 "max_output_tokens_per_request": 100, "max_wall_seconds_per_run": 1}))
    first = LiveRuntime(config)
    assert first._budget("run_1") == 3
    restarted = LiveRuntime(config)
    assert restarted._budget("run_2") == 1
    with pytest.raises(ValueError, match="MODEL_REQUEST_BUDGET"):
        restarted._budget("run_3")
    restarted._budget("run_2", 0)
    assert restarted._budget("run_3") == 1
    with pytest.raises(ValueError, match="MODEL_ALLOCATION_ALREADY_USED"):
        restarted._budget("run_1")
    values = json.loads(config.read_text())
    values["max_total_requests"] = None
    config.write_text(json.dumps(values))
    unlimited = LiveRuntime(config)
    assert unlimited._budget("chat_once", reserve_count=1) == 1
    assert LiveRuntime(config).used == unlimited.used
    with pytest.raises(ValueError, match="INVALID_MODEL_BUDGET"):
        unlimited._budget("chat_invalid", reserve_count=4)
    assert unlimited._budget("run_unlimited") == 3
    assert unlimited.used > 4  # Preserve previous usage without blocking a new bounded run.
    service = ApiService(tmp_path / "offline-runs")
    try:
        rid = service.runner.create_campaign("dual_route_stale")["run_id"]
        with pytest.raises(ValueError, match="LIVE_CAMPAIGN_REQUIRED"):
            restarted.execute(service, rid)
    finally:
        service.close()


def test_mock_provider_failure_retains_live_infrastructure_error_and_no_false_success(tmp_path):
    class MockFailure:
        def execute(self, *_args):
            raise RuntimeError("OFFLINE_FIXTURE_FAILURE")

    app = create_app(tmp_path)
    app.state.service.live = MockFailure()
    with TestClient(app) as client:
        create = {"config_id": "dual_route_stale", "request_id": "offline_fixture", "runtime_mode": "LIVE_AGNES"}
        rid = client.post("/api/v1/runs", json=create).json()["state"]["run_id"]
        base = f"/api/v1/runs/{rid}"
        for _ in range(100):
            if not client.get(base).json()["job_active"]:
                break
            time.sleep(0.01)
        report = client.get(base + "/report").json()
        assert report["status"] == "ERROR" and report["verdict"] == "INCONCLUSIVE"
        assert report["model_requests"] is None and report["reached_count"] == 0
        assert client.get(base).json()["execution_error"] == {"code": "EXECUTION_ERROR"}
        with zipfile.ZipFile(io.BytesIO(client.get(base + "/export").content)) as archive:
            assert json.loads(archive.read("execution_error.json")) == {"code": "EXECUTION_ERROR"}
        assert client.get(base + "/agh").status_code == 409
        assert client.post("/api/v1/runs", json={**create, "request_id": "manual", "execution_mode": "manual"}).status_code == 422


def test_mock_live_cancel_waits_for_worker_before_sealing_unknown_usage(tmp_path):
    entered, release = threading.Event(), threading.Event()

    class MockWaiting:
        def execute(self, service, rid):
            entered.set()
            assert release.wait(5)
            assert service.runner._get(rid)["cancel"].is_set()

    app = create_app(tmp_path)
    app.state.service.live = MockWaiting()
    with TestClient(app) as client:
        rid = client.post("/api/v1/runs", json={"config_id": "dual_route_stale", "request_id": "cancel_fixture",
                                               "runtime_mode": "LIVE_AGNES"}).json()["state"]["run_id"]
        assert entered.wait(2)
        base = f"/api/v1/runs/{rid}"
        try:
            stopped = client.post(base + "/stop", json={}).json()
            assert stopped["state"]["status"] == "CANCELLED"
            assert not stopped["report_available"]
        finally:
            release.set()
        for _ in range(100):
            if not client.get(base).json()["job_active"]:
                break
            time.sleep(0.01)
        report = client.get(base + "/report").json()
        assert report["status"] == "CANCELLED" and report["model_requests"] is None


@pytest.mark.parametrize(("facts", "rows", "expected"), [
    ({"error_code": "TIMEOUT"}, [], "MODEL_REQUEST_TIMEOUT"),
    ({"error_code": "RATE_LIMIT"}, [], "MODEL_RATE_LIMIT"),
    ({"error_code": "QUOTA"}, [], "MODEL_QUOTA_EXHAUSTED"),
    ({"error_code": "AUTH"}, [], "MODEL_AUTH_ERROR"),
    ({"error_code": "TRANSPORT"}, [], "MODEL_TRANSPORT_ERROR"),
    ({"reason": "aborted"}, [{"failure": {"code": "MODEL_REQUEST_TIMEOUT"}}], "MODEL_REQUEST_TIMEOUT"),
    ({"reason": "error", "code": "E_STEP_FAILED"},
     [{"type": "guard_failure", "code": "MODEL_REQUEST_BUDGET"}], "MODEL_REQUEST_BUDGET"),
    ({"error_code": "QUOTA"}, [{"failure": {"code": "MODEL_REQUEST_TIMEOUT"}}], "MODEL_QUOTA_EXHAUSTED"),
    ({"error_code": "PRIVATE_SECRET"}, [], "AGH_FLOW_INCOMPLETE"),
])
def test_terminal_failure_classification(facts, rows, expected):
    assert execution_failure({"status": "COMPLETED"}, facts, rows) == expected
    assert execution_failure({"status": "TIMEOUT"}, facts, rows) == "WALL_TIME_EXHAUSTED"


@pytest.mark.parametrize("code", ["MODEL_REQUEST_TIMEOUT", "MODEL_RATE_LIMIT", "MODEL_QUOTA_EXHAUSTED",
                                   "MODEL_REQUEST_BUDGET", "WALL_TIME_EXHAUSTED"])
def test_precise_live_errors_survive_api_report_and_export(tmp_path, monkeypatch, code):
    monkeypatch.delenv("WORLDGUARD_LIVE_CONFIG", raising=False)

    class MockFailure:
        def __init__(self):
            self.config = {"max_wall_seconds_per_run": 300}

        def execute(self, service, rid):
            assert service.runner._get(rid)["config"]["max_seconds"] == 300
            raise RuntimeError(code)

    app = create_app(tmp_path)
    app.state.service.live = MockFailure()
    with TestClient(app) as client:
        rid = client.post("/api/v1/runs", json={"config_id": "dual_route_stale",
                          "request_id": code, "runtime_mode": "LIVE_AGNES"}).json()["state"]["run_id"]
        app.state.service.jobs[rid].result(timeout=5)
        base = f"/api/v1/runs/{rid}"
        assert client.get(base).json()["execution_error"] == {"code": code}
        report = client.get(base + "/report").json()
        assert report["status"] == "ERROR" and report["reached_count"] == 0
        with zipfile.ZipFile(io.BytesIO(client.get(base + "/export").content)) as archive:
            assert json.loads(archive.read("execution_error.json")) == {"code": code}


def test_live_deadline_starts_after_queue_and_propagates_to_every_layer(tmp_path, monkeypatch):
    runtime_root = tmp_path / "agh"
    tsx = runtime_root / "node_modules/tsx/dist/cli.mjs"
    tsx.parent.mkdir(parents=True)
    tsx.write_text("// offline fixture")
    monkeypatch.setattr("subprocess.run", lambda *a, **k: type("Result", (), {"stdout": PINNED_AGH})())
    config = tmp_path / "budget.local.json"
    values = {"external_model_calls_allowed": True, "approval_reference": "OFFLINE_TEST",
              "agh_root": str(runtime_root), "credential_home": str(tmp_path),
              "max_total_requests": 4, "max_requests_per_run": 3,
              "max_output_tokens_per_request": 100, "max_wall_seconds_per_run": 300,
              "request_timeout_seconds": 90}
    config.write_text(json.dumps(values))
    live = LiveRuntime(config)
    live.root = tmp_path

    class MockMcp:
        url = "http://127.0.0.1:1/mcp"
        finish_requested = False

        def __init__(self, *args):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    def mock_host(argv, **kwargs):
        from pathlib import Path
        recipe = json.loads(Path(argv[-1]).read_text(encoding="utf-8"))
        assert recipe["wall_seconds"] == 300
        assert recipe["request_timeout_seconds"] == 90
        assert 298_000 < recipe["deadline_epoch_ms"] - time.time() * 1000 <= 300_000
        assert kwargs["timeout_seconds"] == 330
        assert service.runner._public(service.runner._get(rid))["elapsed_seconds"] < 2
        return {"status": "COMPLETED", "exit_code": 1, "stderr": "",
                "stdout": json.dumps({"type": "failure", "code": "TIMEOUT", "model_requests": 1})}

    monkeypatch.setattr("worldguard.live_runtime.BoundMcp", MockMcp)
    monkeypatch.setattr("worldguard.live_runtime.run_local_process", mock_host)
    service = ApiService(tmp_path / "runs", live=live)
    try:
        rid = service.runner.create_campaign("dual_route_stale", "LIVE_AGNES")["run_id"]
        service.runner._get(rid)["started"] -= 600
        with pytest.raises(RuntimeError, match="MODEL_REQUEST_TIMEOUT"):
            live.execute(service, rid)
        assert service.runner._get(rid)["config"]["max_seconds"] == 300
        assert live.used == 1
        offline = service.runner.create_campaign("dual_route_stale")
        assert offline["config"]["max_seconds"] == 120
    finally:
        service.close()
    for bad in (0, True, 301):
        config.write_text(json.dumps({**values, "request_timeout_seconds": bad}))
        with pytest.raises(ValueError, match="INVALID_REQUEST_TIMEOUT"):
            LiveRuntime(config)
