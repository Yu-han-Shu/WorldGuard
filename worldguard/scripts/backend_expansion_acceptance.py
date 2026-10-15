"""Reproduce the complex-map matrix through HTTP contracts without model calls."""

import argparse
import io
import json
import secrets
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from worldguard.api import create_app
from worldguard.campaign.runner import CONFIGS
from worldguard.scene import COMPLEX_FAMILIES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("artifacts/batches/BACKEND_EXPANSION"))
    args = parser.parse_args()
    target = args.output / ("matrix_" + secrets.token_hex(4))
    target.mkdir(parents=True, exist_ok=False)
    app = create_app(target / "runs")
    rows = []
    with TestClient(app) as client:
        for cid, config in CONFIGS.items():
            if config["family"] not in COMPLEX_FAMILIES:
                continue
            response = client.post("/api/v1/runs", json={"config_id": cid, "request_id": cid,
                                                         "tester": "AdaptiveRule"})
            assert response.status_code == 201, response.text
            rid = response.json()["state"]["run_id"]
            app.state.service.jobs[rid].result(timeout=30)
            base = f"/api/v1/runs/{rid}"
            report = client.get(base + "/report").json()
            assert report["status"] == "COMPLETED", report
            assert report["executed_cases"] == report["planned_cases"]
            assert report["model_requests"] == 0
            for case in report["results"]:
                case_id = case["case_id"]
                path = base + f"/cases/{case_id}"
                response = client.post(path + "/optimize")
                assert response.status_code == 200, response.text
                result = response.json()
                assert result["planner_evaluations"] == 4
                assert all(c["audit"]["status"] == "PASS" for c in result["candidates"] if c["eligible"])
                assert result["task_hash"] == report["task_hash"]
                assert result["constraints_hash"] == report["constraints_hash"]
                if config["stale_view"] and case_id != "normal":
                    assert case["original_audit"]["status"] == "FAIL"
                expected = "SAFE_STOP" if config["family"] == "switchback" and case_id != "normal" else "REACHED"
                assert case["navigation_status"] == expected
                rows.append({"config_id": cid, "run_id": rid, "case_id": case_id,
                             "navigation_status": expected, "original_audit": case["original_audit"]["status"],
                             "decision": result["decision"], "selected_profile": result["selected_profile"],
                             "score_improvement": result["score_improvement"], "metric_changes": result["metric_changes"]})
                (target / f"{cid}_{case_id}.svg").write_bytes(client.get(path + "/map.svg").content)
            raw = client.get(base + "/export").content
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                assert len([n for n in archive.namelist() if n.startswith("optimization/")]) == report["planned_cases"]
            (target / f"{cid}.zip").write_bytes(raw)
            print(json.dumps({"config": cid, "cases": report["executed_cases"], "status": "PASS"}), flush=True)
    summary = {"evidence_level": "INTEGRATION_TEST", "model_requests": 0,
               "runs": len({r["run_id"] for r in rows}), "cases": len(rows), "planner_evaluations": 4 * len(rows),
               "improved": sum(r["decision"] == "IMPROVED" for r in rows),
               "no_improvement": sum(r["decision"] == "NO_IMPROVEMENT" for r in rows),
               "no_safe_path": sum(r["decision"] == "NO_SAFE_PATH" for r in rows), "rows": rows}
    (target / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}), flush=True)
    print(str(target / "summary.json"), flush=True)


if __name__ == "__main__":
    main()
