"""Real loopback HTTP -> official AGH -> Agnes -> authenticated MCP -> core -> report/ZIP."""

import argparse
import hashlib
import io
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--config", default="configs/model_budget.local.json")
parser.add_argument("--configs", nargs="+", default=["dual_route_stale", "single_entry_stale", "corridor_stale"])
parser.add_argument("--port", type=int, default=8521)
parser.add_argument("--existing", nargs="*", default=[])
parser.add_argument("--output", type=Path, help="Separate evidence directory for this acceptance batch")
parser.add_argument("--require-optimization", action="store_true", help="Require an actual AGH-linked optimization call")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
base = f"http://127.0.0.1:{args.port}"
env = dict(os.environ, WORLDGUARD_LIVE_CONFIG=str(Path(args.config).resolve()))
env["WORLDGUARD_RUNS_DIR"] = str(root / "artifacts/live-campaigns")
output = args.output.resolve() if args.output else root / "artifacts/batches/AGH_LIVE"
output.mkdir(parents=True, exist_ok=True)
budget = json.loads(Path(args.config).read_text(encoding="utf-8"))
acceptance_timeout = budget["max_wall_seconds_per_run"] + 45


def request(path, body=None, *, raw=False):
    payload = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as response:
        value = response.read()
    return value if raw else json.loads(value)


with (output / "api_server.local.log").open("w", encoding="utf-8") as log:
    process = subprocess.Popen([sys.executable, "-m", "uvicorn", "worldguard.api:create_app", "--factory",
                                "--host", "127.0.0.1", "--port", str(args.port), "--log-level", "error"],
                               env=env, stdout=log, stderr=log,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    results = []
    try:
        deadline = time.monotonic() + 20
        while True:
            try:
                health = request("/api/v1/health")
                assert health["external_model_calls_allowed"]
                break
            except (OSError, AssertionError):
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("LIVE_API_START_FAILED") from None
                time.sleep(0.1)
        targets = [(None, rid) for rid in args.existing] + [(config, None) for config in args.configs]
        for config, existing in targets:
            run = request(f"/api/v1/runs/{existing}") if existing else request("/api/v1/runs", {
                "config_id": config, "request_id": secrets.token_hex(12),
                "runtime_mode": "LIVE_AGNES", "execution_mode": "automatic"})
            config = run["config_id"]
            rid = run["state"]["run_id"]
            print(json.dumps({"started": rid, "config": config}), flush=True)
            path = f"/api/v1/runs/{rid}"
            deadline = time.monotonic() + acceptance_timeout
            while request(path)["job_active"]:
                if time.monotonic() > deadline:
                    request(path + "/stop", {})
                    raise RuntimeError("LIVE_ACCEPTANCE_TIMEOUT")
                time.sleep(0.5)
            report = request(path + "/report")
            session = request(path + "/agh")
            fact = {"run_id": rid, "config": config, "status": report["status"],
                    "execution_error": request(path).get("execution_error"),
                    "reached_count": report["reached_count"], "safe_stop_count": report["safe_stop_count"],
                    "executed_cases": report["executed_cases"], "model_requests": report["model_requests"],
                    "optimization_evaluations": report.get("optimization_evaluations", 0),
                    "optimizations": report.get("optimizations", []),
                    "model_tokens": report["model_tokens"], "agh_session_id": session.get("session_id"),
                    "nonce_round_trip": session.get("trace", {}).get("nonce_round_trip"),
                    "original_fail_count": sum(r["original_audit"]["status"] == "FAIL" for r in report["results"])}
            results.append(fact)
            (output / "live_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
            print(json.dumps(fact), flush=True)
            assert report["status"] == "COMPLETED", fact
            assert session["trace"]["nonce_round_trip"], fact
            assert session["trace"]["provenance"] == "CAPTURED_OFFICIAL_HOST"
            assert report["model_requests"] > 0
            assert report["executed_cases"] == report["planned_cases"]
            if args.require_optimization:
                assert report.get("optimizations"), "AGENT_OPTIMIZATION_NOT_OBSERVED"
                assert 4 <= report["optimization_evaluations"] <= 8
                links = session["trace"]["product_event_links"]
                assert any(link["tool"] == "wg_optimize_case" for link in links)
                for optimization in report["optimizations"]:
                    assert optimization["applied_to_navigation"] is False
                    assert optimization["task_hash"] == report["task_hash"]
                    assert optimization["constraints_hash"] == report["constraints_hash"]
            if config == "dual_route_stale":
                assert fact["original_fail_count"] >= 1 and report["reached_count"] == 2, fact
            if config == "single_entry_stale":
                assert report["safe_stop_count"] == 1 and report["reached_count"] == 1, fact
            events = request(path + "/events")
            assert all(e["runtime_mode"] == "LIVE_AGNES" for e in events["items"])
            data = request(path + "/export", raw=True)
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                ledger = archive.read("agh_session.jsonl")
                assert hashlib.sha256(ledger).hexdigest() == session["ledger_sha256"]
                assert "agh_summary.json" in archive.namelist()
                if args.require_optimization:
                    for optimization in report["optimizations"]:
                        full = json.loads(archive.read("optimization/" + optimization["case_id"] + ".json"))
                        assert full["decision"] == optimization["decision"]
                        assert full["selected_profile"] == optimization["selected_profile"]
                        assert full["scene_hash"] == optimization["scene_hash"]
            for case in report["results"]:
                svg = request(path + f"/cases/{case['case_id']}/map.svg", raw=True)
                assert b"<svg" in svg
        print(json.dumps({"status": "LIVE_MINIMAL_CHAIN_PASS", "campaigns": len(results)}), flush=True)
    finally:
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
