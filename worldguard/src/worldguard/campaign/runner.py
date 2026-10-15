import datetime
import json
import re
import threading
import time
import uuid
from dataclasses import asdict
from pathlib import Path

from worldguard.contracts import digest, identifier
from worldguard.evidence import write_json
from worldguard.faults import CaseSpec, inject
from worldguard.optimization import optimize
from worldguard.planners.reference_astar import ReferenceAStar
from worldguard.reports import markdown_report
from worldguard.scene import COMPLEX_FAMILIES, DEV_SEEDS, FAULT_KINDS, complex_layout, make_scene
from worldguard.verifier.audit import audit_path

CONFIGS = {
    f"{family}_{view}": {
        "family": family,
        "stale_view": view == "stale",
        "seed": 11,
        "max_actions": 12,
        "max_recoveries_per_case": 2,
        "max_seconds": 120,
        "max_tools": 200,
    }
    for family in ("dual_route", "corridor", "single_entry")
    for view in ("stale", "current")
}
for family in COMPLEX_FAMILIES:
    for seed in DEV_SEEDS:
        for view in ("stale", "current"):
            cid = f"{family}_{view}" if seed == 11 else f"{family}_s{seed}_{view}"
            CONFIGS[cid] = {**CONFIGS[f"dual_route_{view}"], "family": family, "seed": seed}


class CampaignError(ValueError):
    pass


def configuration(config_id):
    """Resolve approved catalogue or versioned, bounded procedural geometry; no arbitrary config."""
    if config_id in CONFIGS:
        return dict(CONFIGS[config_id])
    match = re.fullmatch(r"generated_v1_s([0-9]{1,10})_stale", config_id)
    if match and int(match[1]) <= 2**31 - 1:
        return {**CONFIGS["generated_stale"], "seed": int(match[1])}
    match = re.fullmatch(r"generated_v2_s([0-9]{1,10})_stale", config_id)
    if match and int(match[1]) <= 2**31 - 1:
        return {**CONFIGS["challenge_stale"], "seed": int(match[1])}
    raise CampaignError("CONFIG_NOT_APPROVED")


class CampaignRunner:
    """One in-memory owner per session; no tool accepts filesystem paths or arbitrary config."""

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.runs = {}
        self.lock = threading.RLock()

    def _get(self, run_id):
        identifier(run_id)
        if run_id not in self.runs:
            raise CampaignError("UNKNOWN_RUN_OR_WRONG_SESSION")
        return self.runs[run_id]

    def _event(self, run, tool, inputs, output, case_id=None, request_id=None):
        event = {
            "event_id": "event_" + uuid.uuid4().hex,
            "run_id": run["run_id"],
            "case_id": case_id,
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "tool_name": tool,
            "request_id": request_id,
            "input_hash": digest(inputs),
            "output_hash": digest(output),
            "status": run["status"],
            "artifact_refs": [],
            "runtime_mode": run.get("runtime_mode", "DETERMINISTIC"),
        }
        run["events"].append(event)
        with (run["directory"] / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event) + "\n")
        write_json(run["directory"] / "state.json", self._public(run))

    def _public(self, run):
        now = time.monotonic()
        end = now if run["status"] == "RUNNING" else run.setdefault("finished", now)
        return {
            "run_id": run["run_id"],
            "status": run["status"],
            "runtime_mode": run.get("runtime_mode", "DETERMINISTIC"),
            "config": dict(run["config"]),
            "sut_executions": run["actions"],
            "remaining_actions": run["config"]["max_actions"] - run["actions"],
            "tool_calls": run["tools"],
            "optimization_evaluations": run.get("optimization_evaluations", 0),
            "max_optimization_evaluations": 8,
            **run.get("model_usage", {"model_requests": 0, "model_tokens": None, "model_cost": None}),
            "task_hash": run["task"].task_hash,
            "constraints_hash": run["task"].robot.constraints_hash,
            "elapsed_seconds": end - run["started"],
        }

    def _guard(self, run, action=False):
        if run["cancel"].is_set() or run["status"] != "RUNNING":
            raise CampaignError("CAMPAIGN_NOT_RUNNING")
        if time.monotonic() - run["started"] >= run["config"]["max_seconds"]:
            run["status"] = "BLOCKED"
            write_json(run["directory"] / "state.json", self._public(run))
            raise CampaignError("WALL_TIME_BUDGET_EXHAUSTED")
        if run["tools"] >= run["config"]["max_tools"]:
            raise CampaignError("TOOL_BUDGET_EXHAUSTED")
        if action and run["actions"] >= run["config"]["max_actions"]:
            raise CampaignError("SUT_BUDGET_EXHAUSTED")
        run["tools"] += 1
        if action:
            run["actions"] += 1

    def _case(self, run, case_id):
        identifier(case_id)
        if case_id not in run["candidates"]:
            raise CampaignError("UNKNOWN_CASE")
        return run["candidates"][case_id]

    def _evidence(self, run, value):
        evidence_id = "evidence_" + uuid.uuid4().hex
        run["evidence"][evidence_id] = value
        write_json(run["directory"] / "evidence" / (evidence_id + ".json"), value)
        return evidence_id

    def create_campaign(self, config_id, runtime_mode="DETERMINISTIC"):
        with self.lock:
            if runtime_mode not in ("DETERMINISTIC", "LIVE_AGNES"):
                raise CampaignError("INVALID_RUNTIME_MODE")
            config = configuration(config_id)
            if len(self.runs) >= 50:
                raise CampaignError("SESSION_CAMPAIGN_LIMIT")
            scene, task = make_scene(config["family"], config["seed"])
            run_id = "run_" + uuid.uuid4().hex
            directory = self.root / run_id
            directory.mkdir(parents=True, exist_ok=False)
            (directory / "evidence").mkdir()
            kind = FAULT_KINDS[config["family"]]
            cases = {"normal": CaseSpec("normal", scene.content_hash, "NONE", config["seed"])}
            severities = range(1, 5) if kind == "PINCH_CLEARANCE" else (1,)
            if config["family"] in COMPLEX_FAMILIES:
                severities = range(1, len(complex_layout(config["family"], config["seed"])[-1]) + 1)
            for severity in severities:
                cid = f"{kind.lower()}_{severity}"
                cases[cid] = CaseSpec(cid, scene.content_hash, kind, config["seed"], severity)
            run = {
                "run_id": run_id,
                "config_id": config_id,
                "runtime_mode": runtime_mode,
                "model_usage": {"model_requests": 0 if runtime_mode == "DETERMINISTIC" else None,
                                "model_tokens": None, "model_cost": None},
                "directory": directory,
                "config": config,
                "scene": scene,
                "task": task,
                "candidates": cases,
                "evidence": {},
                "plans": {},
                "audits": {},
                "requests": {},
                "recoveries": {},
                "stopped": set(),
                "cancel": threading.Event(),
                "events": [],
                "status": "RUNNING",
                "actions": 0,
                "tools": 0,
                "optimizations": {},
                "optimization_evaluations": 0,
                "started": time.monotonic(),
            }
            self.runs[run_id] = run
            out = self._public(run)
            self._event(run, "wg_create_campaign", {"config_id": config_id}, out)
            return out

    def list_candidates(self, run_id):
        with self.lock:
            run = self._get(run_id)
            self._guard(run)
            result = [
                {"case_id": c.case_id, "fault": c.kind, "severity": c.severity}
                for c in run["candidates"].values()
            ]
            self._event(run, "wg_list_candidates", {}, result)
            return result

    def publish_decision(self, run_id, phase, summary, case_id, evidence_ids, case_order):
        """Public action summary, never a private reasoning transcript or safety verdict."""
        with self.lock:
            run = self._get(run_id)
            if phase not in ("PLAN", "FINDING", "RECOVERY", "COMPLETE"):
                raise CampaignError("INVALID_DECISION_PHASE")
            if not isinstance(summary, str) or not 1 <= len(summary.strip()) <= 320:
                raise CampaignError("INVALID_DECISION_SUMMARY")
            if case_id:
                self._case(run, case_id)
            if len(evidence_ids) > 5 or len(case_order) > 5 or len(set(case_order)) != len(case_order):
                raise CampaignError("INVALID_DECISION_REFERENCES")
            for cid in case_order:
                self._case(run, cid)
            for eid in evidence_ids:
                value = run["evidence"].get(identifier(eid))
                if not value or (case_id and value.get("case_id") != case_id):
                    raise CampaignError("INVALID_DECISION_EVIDENCE")
            if phase in ("FINDING", "RECOVERY") and not evidence_ids:
                raise CampaignError("DECISION_EVIDENCE_REQUIRED")
            self._guard(run)
            inputs = {"phase": phase, "summary": summary, "case_id": case_id,
                      "evidence_ids": evidence_ids, "case_order": case_order}
            out = {**inputs, "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
                   "source": "AGNES_AGH" if run["runtime_mode"] == "LIVE_AGNES" else "RULE_CONTROLLER"}
            run.setdefault("agent_decisions", []).append(out)
            write_json(run["directory"] / "agent_decisions.json", run["agent_decisions"])
            self._event(run, "wg_publish_decision", inputs, out, case_id or None)
            return out

    def _idempotent(self, run, request_id, payload, operation):
        identifier(request_id)
        key = digest(payload)
        if request_id in run["requests"]:
            old_key, value = run["requests"][request_id]
            if old_key != key:
                raise CampaignError("REQUEST_ID_CONFLICT")
            return json.loads(json.dumps(value))
        output = operation()
        run["requests"][request_id] = (key, output)
        return json.loads(json.dumps(output))

    def _plan(self, run, case, view, role):
        self._guard(run, action=True)
        strategy = run["config"].get("navigation_strategy")
        if strategy:
            from worldguard.planners.strategy_astar import Strategy, StrategyAStar
            planner = StrategyAStar(Strategy(strategy["turn_cost_m"], strategy["clearance_weight"]))
            result = planner.plan(view, run["task"], cancel=run["cancel"],
                                  timeout=max(0.01, min(20, run["config"]["max_seconds"] - (time.monotonic() - run["started"]))))
        else:
            result = ReferenceAStar().plan(view, run["task"])
        path_id = "path_" + uuid.uuid4().hex
        record = {"case_id": case.case_id, "path_id": path_id, "role": role, "plan": asdict(result)}
        if strategy:
            record["submission_id"] = run["config"]["submission_id"]
            record["strategy_hash"] = digest(strategy)
        evidence_id = self._evidence(run, record)
        run["plans"][path_id] = record
        return {**record, "evidence_id": evidence_id, "audit_status": "NOT_RUN"}

    def run_case(self, run_id, case_id, request_id, rerun=False):
        with self.lock:
            run = self._get(run_id)
            case = self._case(run, case_id)
            payload = {"case_id": case_id, "operation": "rerun" if rerun else "run"}

            def operation():
                previous = [p for p in run["plans"].values() if p["case_id"] == case_id]
                if rerun and not previous:
                    raise CampaignError("CASE_NOT_YET_RUN")
                if previous and not rerun:
                    raise CampaignError("USE_RERUN_FOR_EXISTING_CASE")
                current = inject(run["scene"], case)
                view = run["scene"] if run["config"]["stale_view"] else current
                out = self._plan(run, case, view, "rerun" if rerun else "original")
                self._event(
                    run, "wg_rerun_case" if rerun else "wg_run_case", payload, out, case_id, request_id
                )
                return out

            return self._idempotent(run, request_id, payload, operation)

    def audit_path(self, run_id, case_id, path_id):
        with self.lock:
            run = self._get(run_id)
            case = self._case(run, case_id)
            identifier(path_id)
            record = run["plans"].get(path_id)
            if not record or record["case_id"] != case_id:
                raise CampaignError("UNKNOWN_PATH")
            if path_id in run["audits"]:
                return run["audits"][path_id]
            self._guard(run)
            audit = audit_path(inject(run["scene"], case), run["task"], record["plan"]["path"])
            value = {"case_id": case_id, "path_id": path_id, "audit": audit}
            result = {**value, "evidence_id": self._evidence(run, value)}
            run["audits"][path_id] = result
            self._event(run, "wg_audit_path", {"path_id": path_id}, result, case_id)
            return result

    def recover_case(self, run_id, case_id, action, evidence_ids, request_id):
        with self.lock:
            run = self._get(run_id)
            case = self._case(run, case_id)
            if action not in ("REFRESH_MAP_REPLAN", "RETRY_TRANSIENT_ONCE", "SAFE_STOP"):
                raise CampaignError("ACTION_NOT_ALLOWED")
            if not isinstance(evidence_ids, list) or not 1 <= len(evidence_ids) <= 10:
                raise CampaignError("AUDIT_EVIDENCE_REQUIRED")
            for evidence_id in evidence_ids:
                value = run["evidence"].get(identifier(evidence_id))
                if not value or value.get("case_id") != case_id or "audit" not in value:
                    raise CampaignError("AUDIT_EVIDENCE_REQUIRED")
            payload = {"case_id": case_id, "action": action, "evidence_ids": evidence_ids}

            def operation():
                if case_id in run["stopped"]:
                    raise CampaignError("CASE_ALREADY_STOPPED")
                if action == "RETRY_TRANSIENT_ONCE":
                    # This deterministic adapter has no transient-error return code.
                    raise CampaignError("NO_TRANSIENT_FAILURE_TO_RETRY")
                if action == "SAFE_STOP":
                    self._guard(run)
                    run["stopped"].add(case_id)
                    out = {
                        "case_id": case_id,
                        "navigation_status": "SAFE_STOP",
                        "reached": False,
                        "reason_code": "INCONCLUSIVE_STOP",
                    }
                else:
                    count = run["recoveries"].get(case_id, 0)
                    if count >= run["config"]["max_recoveries_per_case"]:
                        raise CampaignError("RECOVERY_BUDGET_EXHAUSTED")
                    out = self._plan(run, case, inject(run["scene"], case), "recovery")
                    run["recoveries"][case_id] = count + 1
                self._event(run, "wg_recover_case", payload, out, case_id, request_id)
                return out

            return self._idempotent(run, request_id, payload, operation)

    def optimize_case(self, run_id, case_id, evidence_id, request_id):
        """Compare four fixed strategies after an observed audit; never rewrite navigation results."""
        with self.lock:
            run = self._get(run_id)
            case = self._case(run, case_id)
            evidence = run["evidence"].get(identifier(evidence_id))
            if not evidence or evidence.get("case_id") != case_id or "audit" not in evidence:
                raise CampaignError("AUDIT_EVIDENCE_REQUIRED")
            payload = {"case_id": case_id, "evidence_id": evidence_id}

            def operation():
                if case_id in run["optimizations"]:
                    self._guard(run)
                    out = run["optimizations"][case_id]
                else:
                    if run["optimization_evaluations"] + 4 > 8:
                        raise CampaignError("OPTIMIZATION_BUDGET_EXHAUSTED")
                    self._guard(run)
                    run["optimization_evaluations"] += 4  # Reserve before work, including interrupted attempts.
                    write_json(run["directory"] / "state.json", self._public(run))
                    remaining = run["config"]["max_seconds"] - (time.monotonic() - run["started"])
                    result = {"run_id": run_id, "case_id": case_id,
                              **optimize(inject(run["scene"], case), run["task"],
                                         cancel=run["cancel"], timeout=min(40, remaining))}
                    if run["cancel"].is_set():
                        raise CampaignError("OPTIMIZATION_CANCELLED")
                    if time.monotonic() - run["started"] >= run["config"]["max_seconds"]:
                        raise CampaignError("WALL_TIME_BUDGET_EXHAUSTED")
                    result_id = self._evidence(run, result)
                    out = {k: result[k] for k in ("run_id", "case_id", "decision", "selected_profile",
                            "score_improvement", "scene_hash", "task_hash", "constraints_hash", "planner_evaluations",
                            "metric_changes", "selection_reason")}
                    out.update(evidence_id=result_id, based_on_evidence_id=evidence_id,
                               applied_to_navigation=False,
                               candidates=[{k: c[k] for k in ("profile", "eligible", "score", "metrics")}
                                           | {"audit_status": c["audit"]["status"], "selection_reason": c["selection_reason"]}
                                           for c in result["candidates"]])
                    target = run["directory"] / "optimization" / (case_id + ".json")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    temporary = target.with_suffix(".tmp")
                    write_json(temporary, result)
                    temporary.replace(target)
                    run["optimizations"][case_id] = out
                self._event(run, "wg_optimize_case", payload, out, case_id, request_id)
                return out

            return self._idempotent(run, request_id, payload, operation)

    def read_evidence(self, run_id, evidence_id):
        with self.lock:
            run = self._get(run_id)
            identifier(evidence_id)
            if evidence_id not in run["evidence"]:
                raise CampaignError("UNKNOWN_EVIDENCE")
            self._guard(run)
            out = json.loads(json.dumps(run["evidence"][evidence_id]))
            self._event(run, "wg_read_evidence", {"evidence_id": evidence_id}, out)
            return out

    def stop_campaign(self, run_id, reason="USER_CANCELLED"):
        if reason not in ("USER_CANCELLED", "BUDGET_EXHAUSTED", "INFRASTRUCTURE_ERROR"):
            raise CampaignError("INVALID_STOP_REASON")
        run = self._get(run_id)
        run["cancel"].set()  # visible before acquiring lock; prevents subsequent work
        with self.lock:
            if run["status"] == "COMPLETED":
                return self._public(run)
            run["status"] = "CANCELLED"
            out = self._public(run)
            self._event(run, "wg_stop_campaign", {"reason": reason}, out)
            return out

    def finish_campaign(self, run_id):
        with self.lock:
            run = self._get(run_id)
            if "report" in run:
                return run["report"]
            if run["status"] == "RUNNING":
                run["status"] = "COMPLETED"
            results = []
            for cid in run["candidates"]:
                plans = [p for p in run["plans"].values() if p["case_id"] == cid]
                if not plans:
                    continue
                original = next(p for p in plans if p["role"] == "original")
                recoveries = [p for p in plans if p["role"] == "recovery"]
                recovery = recoveries[-1] if recoveries else None
                latest = plans[-1]
                original_audit = run["audits"].get(original["path_id"], {}).get("audit")
                recovery_audit = run["audits"].get(recovery["path_id"], {}).get("audit") if recovery else None
                latest_audit = run["audits"].get(latest["path_id"], {}).get("audit")
                if original_audit is None:
                    original_audit = {
                        "status": "UNKNOWN",
                        "code": "NOT_AUDITED",
                        "binding": None,
                        "violations": [],
                        "epsilon_m": 1e-9,
                    }
                reached = (
                    latest_audit is not None
                    and latest_audit["status"] == "PASS"
                    and cid not in run["stopped"]
                )
                navigation = (
                    "REACHED" if reached else ("SAFE_STOP" if cid in run["stopped"] else "INCOMPLETE")
                )
                result = {
                    "schema_version": "1.0",
                    "run_id": run_id,
                    "case_id": cid,
                    "runtime_mode": run.get("runtime_mode", "DETERMINISTIC"),
                    "execution_status": run["status"],
                    "navigation_status": navigation,
                    "reached": reached,
                    "reason_code": "VERIFIED" if reached else "INCONCLUSIVE_STOP",
                    "original_plan": original["plan"],
                    "submission_id": run["config"].get("submission_id"),
                    "navigation_strategy": run["config"].get("navigation_strategy"),
                    "original_audit": original_audit,
                    "recovery_plan": recovery["plan"] if recovery else None,
                    "recovery_audit": recovery_audit,
                    "oracle": None,
                    "stale_view": run["config"]["stale_view"],
                    "sut_executions": len(plans),
                    "model_requests": 0 if run.get("runtime_mode", "DETERMINISTIC") == "DETERMINISTIC" else None,
                    "model_tokens": None,
                    "model_cost": None,
                    "verdict": "FAILURES_FOUND"
                    if original_audit["status"] == "FAIL"
                    else (
                        "BOUNDED_PASS" if reached and original_audit["status"] == "PASS" else "INCONCLUSIVE"
                    ),
                }
                results.append(result)
                folder = run["directory"] / "cases" / cid
                folder.mkdir(parents=True, exist_ok=False)
                case = run["candidates"][cid]
                payloads = {
                    "scene_before.json": asdict(run["scene"]),
                    "scene_after.json": asdict(inject(run["scene"], case)),
                    "task.json": asdict(run["task"]),
                    "fault.json": asdict(case),
                    "plan.json": original["plan"],
                    "audit.json": original_audit,
                    "result.json": result,
                }
                for name, payload in payloads.items():
                    write_json(folder / name, payload)
                write_json(
                    folder / "manifest.json", {name: digest(value) for name, value in payloads.items()}
                )
                (folder / "report.md").write_text(markdown_report(result), encoding="utf-8")
            if run["status"] == "RUNNING":
                run["status"] = "COMPLETED"
            verdict = (
                "FAILURES_FOUND"
                if any(r["verdict"] == "FAILURES_FOUND" for r in results)
                else (
                    "BOUNDED_PASS"
                    if len(results) == len(run["candidates"])
                    and all(r["verdict"] == "BOUNDED_PASS" for r in results)
                    and run["status"] == "COMPLETED"
                    else "INCONCLUSIVE"
                )
            )
            report = {
                **self._public(run),
                "verdict": verdict,
                "results": results,
                "planned_cases": len(run["candidates"]),
                "executed_cases": len(results),
                "reached_count": sum(r["reached"] for r in results),
                "safe_stop_count": sum(r["navigation_status"] == "SAFE_STOP" for r in results),
                "report_path": "report.json",
                "optimizations": list(run.get("optimizations", {}).values()),
                **({"agh_session": run["agh_session"]} if "agh_session" in run else {}),
            }
            run["report"] = report
            write_json(run["directory"] / "report.json", report)
            (run["directory"] / "report.md").write_text(
                "\n\n---\n\n".join(map(markdown_report, results)), encoding="utf-8"
            )
            self._event(run, "wg_finish_campaign", {}, report)
            return report
