"""HTTP adapter over CampaignRunner; historical runs survive as read-only evidence."""

import datetime
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

from worldguard.campaign.baselines import execute
from worldguard.campaign.runner import CampaignRunner, configuration
from worldguard.contracts import digest, identifier, scene_from, task_from
from worldguard.evidence import read_json, write_json
from worldguard.faults import inject
from worldguard.optimization import optimize
from worldguard.runtime_errors import EXECUTION_CODES


class ApiError(ValueError):
    def __init__(self, code, status=409):
        super().__init__(code)
        self.code, self.status = code, status


class ApiService:
    def __init__(self, root, live=None):
        self.root = Path(root).resolve()
        self.runner = CampaignRunner(self.root)
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="worldguard-api")
        self.jobs = {}
        self.requests = {}
        self.lock = threading.RLock()
        self.chat_lock = threading.Lock()
        self.live = live
        if self.live is None and os.environ.get("WORLDGUARD_LIVE_CONFIG"):
            from worldguard.live_runtime import LiveRuntime
            self.live = LiveRuntime(os.environ["WORLDGUARD_LIVE_CONFIG"])
        for path in self.root.glob("run_*/api_metadata.json"):
            if path.is_symlink() or path.parent.is_symlink():
                continue
            metadata = read_json(path)
            payload = {k: v for k, v in metadata.items() if k != "created_at"}
            self.requests[metadata["request_id"]] = (digest(payload), path.parent.name)

    def close(self):
        for rid, job in list(self.jobs.items()):
            if not job.done():
                self.runner.stop_campaign(rid)
        self.pool.shutdown(wait=True, cancel_futures=True)

    def folder(self, rid):
        identifier(rid)
        folder = (self.root / rid).resolve()
        if folder.parent != self.root or not folder.is_dir() or not (folder / "state.json").is_file():
            raise ApiError("RUN_NOT_FOUND", 404)
        return folder

    def create(self, request):
        if request.runtime_mode == "LIVE_AGNES" and self.live is None:
            raise ApiError("LIVE_NOT_AVAILABLE", 503)
        if request.runtime_mode == "LIVE_AGNES" and request.execution_mode != "automatic":
            raise ApiError("LIVE_REQUIRES_AUTOMATIC", 422)
        if request.runtime_mode == "DETERMINISTIC" and request.tester == "AgnesAGH":
            raise ApiError("AGNES_TESTER_REQUIRES_LIVE", 422)
        configuration(request.config_id)
        from worldguard.missions import read_mission
        mission = read_mission(self.root, request.mission_id) if request.mission_id else None
        from worldguard.submissions import read_submission
        submission = read_submission(self.root, mission["submission_id"]) if mission and mission.get("submission_id") else None
        if submission and (submission["status"] != "READY" or submission["strategy"] != mission.get("navigation_strategy")):
            raise ApiError("SUBMISSION_SCOPE_MISMATCH", 422)
        if mission and (mission["config_id"] != request.config_id or request.execution_mode != "automatic"):
            raise ApiError("MISSION_SCOPE_MISMATCH", 422)
        payload = request.model_dump(exclude_none=True)
        if request.runtime_mode == "LIVE_AGNES":
            payload["tester"] = "AgnesAGH"
        key = digest(payload)
        with self.lock:
            if request.request_id in self.requests:
                old_key, rid = self.requests[request.request_id]
                if old_key != key:
                    raise ApiError("REQUEST_ID_CONFLICT")
                return self.view(rid)
            state = self.runner.create_campaign(request.config_id, request.runtime_mode)
            rid = state["run_id"]
            if mission:
                run = self.runner._get(rid)
                run["mission"] = mission
                if submission:
                    run["config"]["navigation_strategy"] = submission["strategy"]
                    run["config"]["submission_id"] = submission["submission_id"]
                    write_json(run["directory"] / "submission.json", submission)
                run["candidates"] = {cid: run["candidates"][cid] for cid in mission["case_ids"]}
                run["config"]["max_actions"] = mission["max_actions"]
                write_json(run["directory"] / "mission.json", mission)
                self.runner._event(run, "mission_plan_confirmed", {}, mission)
            if request.runtime_mode == "LIVE_AGNES":
                self.runner._get(rid)["config"]["agent_provider"] = getattr(self.live, "config", {}).get("provider", "Agnes")
                wall = getattr(self.live, "config", {}).get("max_wall_seconds_per_run")
                if wall is not None:
                    self.runner._get(rid)["config"]["max_seconds"] = wall
            metadata = {**payload, "created_at": datetime.datetime.now(datetime.UTC).isoformat()}
            write_json(self.folder(rid) / "api_metadata.json", metadata)
            self.requests[request.request_id] = (key, rid)
            self.persist(rid)
            if request.execution_mode == "automatic":
                self.jobs[rid] = self.pool.submit(self._execute, rid, request.tester, request.seed)
            return self.view(rid)

    def _execute(self, rid, tester, seed):
        try:
            if self.runner._get(rid).get("runtime_mode") == "LIVE_AGNES":
                if self.runner._get(rid)["cancel"].is_set():
                    return
                self.live.execute(self, rid)
                self.runner.finish_campaign(rid)
            else:
                execute(self.runner, rid, tester, seed)
        except Exception as error:  # noqa: BLE001 - preserve results at worker boundary
            # No provider/tool exception text enters the public API; keep completed business facts.
            with self.runner.lock:
                run = self.runner._get(rid)
                code = str(error) if str(error) in EXECUTION_CODES else "EXECUTION_ERROR"
                write_json(run["directory"] / "execution_error.json", {"code": code})
                if run["status"] == "RUNNING":
                    run["status"] = "ERROR"
                    self.runner._event(run, "api_execution_error", {}, {"code": code})
                self.runner.finish_campaign(rid)
        finally:
            if self.runner._get(rid)["status"] == "CANCELLED":
                self.runner.finish_campaign(rid)
            self.persist(rid)

    def view(self, rid):
        folder = self.folder(rid)
        metadata = read_json(folder / "api_metadata.json") if (folder / "api_metadata.json").is_file() else {}
        read_only = rid not in self.runner.runs
        if read_only:
            state = read_json(folder / "state.json")
        else:
            with self.runner.lock:
                state = self.runner._public(self.runner._get(rid))
        interrupted = read_only and state["status"] == "RUNNING"
        if interrupted:
            state = {**state, "status": "BLOCKED"}
        base = f"/api/v1/runs/{rid}"
        return {
            "submission": read_json(folder / "submission.json") if (folder / "submission.json").is_file() else None,
            "mission": read_json(folder / "mission.json") if (folder / "mission.json").is_file() else None,
            "agent_decisions": read_json(folder / "agent_decisions.json") if (folder / "agent_decisions.json").is_file() else [],
            "state": state,
            "config_id": metadata.get("config_id"),
            "execution_mode": metadata.get("execution_mode", "legacy"),
            "tester": metadata.get("tester"),
            "read_only": read_only,
            "interrupted": interrupted,
            "job_active": rid in self.jobs and not self.jobs[rid].done(),
            "report_available": (folder / "report.json").is_file(),
            "created_at": metadata.get("created_at"),
            "links": {
                "self": base,
                "candidates": base + "/candidates",
                "events": base + "/events",
                "report": base + "/report",
                "export": base + "/export",
                "agh": base + "/agh",
            },
            "agh_session": read_json(folder / "agh_summary.json") if (folder / "agh_summary.json").is_file() else None,
            "execution_error": read_json(folder / "execution_error.json") if (folder / "execution_error.json").is_file() else None,
        }

    def writable(self, rid):
        self.folder(rid)
        if rid not in self.runner.runs:
            raise ApiError("RUN_READ_ONLY_AFTER_RESTART")
        if rid in self.jobs and not self.jobs[rid].done():
            raise ApiError("AUTOMATIC_RUN_BUSY")

    def action(self, rid, method, *args):
        with self.lock:
            self.writable(rid)
            try:
                return method(rid, *args)
            finally:
                self.persist(rid)

    def stop(self, rid, reason):
        self.folder(rid)
        if rid not in self.runner.runs:
            raise ApiError("RUN_READ_ONLY_AFTER_RESTART")
        # Set cancellation before waiting on the planner's serial lock.
        self.runner.stop_campaign(rid, reason)
        if rid in self.jobs:
            self.jobs[rid].cancel()
        if self.runner._get(rid).get("runtime_mode") != "LIVE_AGNES" or not self.jobs.get(rid) or self.jobs[rid].done():
            self.runner.finish_campaign(rid)
        self.persist(rid)
        return self.view(rid)

    def case_summaries(self, rid):
        run = self.runner._get(rid)
        return [{"case_id": cid, "stopped": cid in run["stopped"],
                 "paths": [{"path_id": p["path_id"], "role": p["role"],
                            "audit_status": run["audits"].get(p["path_id"], {}).get("audit", {}).get("status")}
                           for p in run["plans"].values() if p["case_id"] == cid]}
                for cid in run["candidates"]]

    def _snapshot(self, rid):
        with self.runner.lock:
            run = self.runner._get(rid)
            cases = {}
            for cid, candidate in run["candidates"].items():
                records = []
                for record in run["plans"].values():
                    if record["case_id"] != cid:
                        continue
                    audit = run["audits"].get(record["path_id"])
                    evidence_id = next(
                        (
                            eid
                            for eid, value in run["evidence"].items()
                            if value.get("path_id") == record["path_id"] and "plan" in value
                        ),
                        None,
                    )
                    records.append(
                        {
                            **record,
                            "evidence_id": evidence_id,
                            "audit": audit,
                            "audit_status": audit["audit"]["status"] if audit else "NOT_RUN",
                        }
                    )
                after = inject(run["scene"], candidate)
                result = next(
                    (r for r in run.get("report", {}).get("results", []) if r["case_id"] == cid), None
                )
                cases[cid] = {
                    "run_id": rid,
                    "candidate": {"case_id": cid, "fault": candidate.kind, "severity": candidate.severity},
                    "scene_before": {**asdict(run["scene"]), "content_hash": run["scene"].content_hash},
                    "scene_after": {**asdict(after), "content_hash": after.content_hash},
                    "task": asdict(run["task"]),
                    "paths": records,
                    "stopped": cid in run["stopped"],
                    "result": result,
                }
            return {"cases": cases}

    def persist(self, rid):
        with self.runner.lock:
            snapshot = self._snapshot(rid)
            target = self.folder(rid) / "api_snapshot.json"
            temporary = target.with_suffix(".tmp")
            write_json(temporary, snapshot)
            temporary.replace(target)

    def snapshot(self, rid):
        folder = self.folder(rid)
        if rid in self.runner.runs:
            return self._snapshot(rid)
        if (folder / "api_snapshot.json").is_file():
            return read_json(folder / "api_snapshot.json")
        # Legacy completed runs from Streamlit/MCP remain viewable without a migration.
        cases = {}
        for directory in (folder / "cases").glob("*"):
            if not directory.is_dir() or directory.is_symlink():
                continue
            identifier(directory.name)
            result = read_json(directory / "result.json")
            fault = read_json(directory / "fault.json")
            scenes = {
                name: read_json(directory / (name + ".json")) for name in ("scene_before", "scene_after")
            }
            for scene in scenes.values():
                scene["content_hash"] = digest(scene)
            paths = []
            for role, plan, audit in (
                ("original", result["original_plan"], result["original_audit"]),
                ("recovery", result["recovery_plan"], result["recovery_audit"]),
            ):
                if plan is not None:
                    pid = "historical_" + role
                    paths.append(
                        {
                            "case_id": directory.name,
                            "path_id": pid,
                            "role": role,
                            "plan": plan,
                            "audit_status": audit["status"] if audit else "NOT_RUN",
                            "audit": {
                                "case_id": directory.name,
                                "path_id": pid,
                                "audit": audit,
                                "evidence_id": None,
                            }
                            if audit
                            else None,
                        }
                    )
            cases[directory.name] = {
                "run_id": rid,
                "candidate": {
                    "case_id": directory.name,
                    "fault": fault["kind"],
                    "severity": fault["severity"],
                },
                **scenes,
                "task": read_json(directory / "task.json"),
                "paths": paths,
                "stopped": result["navigation_status"] == "SAFE_STOP",
                "result": result,
            }
        return {"cases": cases}

    def case(self, rid, cid):
        identifier(cid)
        value = self.snapshot(rid)["cases"].get(cid)
        if value is None:
            raise ApiError("CASE_NOT_FOUND", 404)
        return value

    def events(self, rid, cursor, limit):
        folder = self.folder(rid)
        if rid in self.runner.runs:
            with self.runner.lock:
                items = list(self.runner._get(rid)["events"])
        else:
            path = folder / "events.jsonl"
            items = (
                [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
                if path.exists()
                else []
            )
        page = items[cursor : cursor + limit]
        next_cursor = cursor + len(page)
        return {"items": page, "next_cursor": next_cursor, "has_more": next_cursor < len(items)}

    def optimization(self, rid, cid, *, create=False):
        # Experiment on frozen inputs; historical campaign outcomes remain unchanged.
        with self.lock:
            case = self.case(rid, cid)
            if self.view(rid)["job_active"]:
                raise ApiError("AUTOMATIC_RUN_BUSY")
            target = self.folder(rid) / "optimization" / (identifier(cid) + ".json")
            if target.is_file():
                return read_json(target)
            if not create:
                raise ApiError("OPTIMIZATION_NOT_READY", 404)
            values = {k: v for k, v in case["scene_after"].items() if k != "content_hash"}
            output = {"run_id": rid, "case_id": cid,
                      **optimize(scene_from(values), task_from(case["task"]))}
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(".tmp")
            write_json(temporary, output)
            temporary.replace(target)
            return output

    def report(self, rid):
        with self.runner.lock:
            folder = self.folder(rid)
            if not (folder / "report.json").is_file():
                raise ApiError("REPORT_NOT_READY")
            return read_json(folder / "report.json")

    def evidence(self, rid, eid):
        identifier(eid)
        path = self.folder(rid) / "evidence" / (eid + ".json")
        if not path.is_file() or path.is_symlink():
            raise ApiError("EVIDENCE_NOT_FOUND", 404)
        return read_json(path)
