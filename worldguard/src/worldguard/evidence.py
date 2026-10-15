"""Append-only case directories with canonical manifests and deterministic replay."""

import json
import time
import uuid
from dataclasses import asdict
from pathlib import Path

from worldguard.contracts import canonical, digest, plan_from, scene_from, task_from
from worldguard.faults import CaseSpec, inject
from worldguard.planners.reference_astar import ReferenceAStar
from worldguard.verifier.audit import audit_path
from worldguard.verifier.oracle import reachable


def write_json(path, value):
    # A polling reader must see one complete version, never a truncated in-flight write.
    destination = Path(path)
    temporary = destination.with_name(destination.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        for attempt in range(6):
            try:
                temporary.replace(destination)
                break
            except PermissionError:
                if attempt == 5:
                    raise
                # Windows readers briefly hold a handle that denies rename.
                time.sleep(0.01)
    finally:
        temporary.unlink(missing_ok=True)


def read_json(path):
    return json.loads(
        Path(path).read_text(encoding="utf-8-sig"),
        parse_constant=lambda x: (_ for _ in ()).throw(ValueError("NON_FINITE_JSON")),
    )


def stable_plan(plan):
    values = asdict(plan) if hasattr(plan, "__dataclass_fields__") else dict(plan)
    values.pop("elapsed_seconds")
    return values


def run_case(scene, task, case, output_root, stale_view=True):
    current = inject(scene, case)
    plan_view = scene if stale_view else current
    planner = ReferenceAStar()
    original = planner.plan(plan_view, task)
    original_audit = audit_path(current, task, original.path)
    recovery, recovery_audit, oracle = None, None, None
    if original_audit["status"] == "PASS":
        navigation, reason = "REACHED", "VERIFIED_ORIGINAL"
    else:
        recovery = planner.plan(current, task)
        recovery_audit = audit_path(current, task, recovery.path)
        if recovery_audit["status"] == "PASS":
            navigation, reason = "REACHED", "REFRESH_MAP_REPLAN_VERIFIED"
        else:
            oracle = reachable(current, task)
            navigation = "SAFE_STOP"
            reason = "NO_PATH_IN_FINITE_GRAPH" if oracle["status"] == "UNREACHABLE" else "INCONCLUSIVE_STOP"
    run_id = "run_" + uuid.uuid4().hex
    case_dir = Path(output_root) / run_id / "cases" / case.case_id
    case_dir.mkdir(parents=True, exist_ok=False)
    result = {
        "schema_version": "1.0",
        "run_id": run_id,
        "case_id": case.case_id,
        "runtime_mode": "DETERMINISTIC",
        "execution_status": "COMPLETED",
        "navigation_status": navigation,
        "reached": navigation == "REACHED",
        "reason_code": reason,
        "original_audit": original_audit,
        "recovery_audit": recovery_audit,
        "original_plan": asdict(original),
        "recovery_plan": asdict(recovery) if recovery else None,
        "oracle": oracle,
        "stale_view": stale_view,
        "sut_executions": 1 + int(recovery is not None),
        "model_requests": 0,
        "model_tokens": None,
        "model_cost": None,
        "verdict": "FAILURES_FOUND"
        if original_audit["status"] == "FAIL"
        else ("BOUNDED_PASS" if original_audit["status"] == "PASS" else "INCONCLUSIVE"),
    }
    payloads = {
        "scene_before.json": asdict(scene),
        "scene_after.json": asdict(current),
        "task.json": asdict(task),
        "fault.json": asdict(case),
        "plan.json": asdict(original),
        "audit.json": original_audit,
        "result.json": result,
    }
    for name, value in payloads.items():
        write_json(case_dir / name, value)
    write_json(case_dir / "manifest.json", {name: digest(value) for name, value in payloads.items()})
    from worldguard.reports import markdown_report

    (case_dir / "report.md").write_text(markdown_report(result), encoding="utf-8")
    return result, case_dir


def replay_case(case_dir, out):
    case_dir, out = Path(case_dir), Path(out)
    manifest = read_json(case_dir / "manifest.json")
    allowed = {
        "scene_before.json",
        "scene_after.json",
        "task.json",
        "fault.json",
        "plan.json",
        "audit.json",
        "result.json",
    }
    if set(manifest) != allowed:
        raise ValueError("MANIFEST_INVALID")
    data = {name: read_json(case_dir / name) for name in allowed}
    if any(digest(data[name]) != expected for name, expected in manifest.items()):
        raise ValueError("EVIDENCE_HASH_MISMATCH")
    scene, current, task = (
        scene_from(data["scene_before.json"]),
        scene_from(data["scene_after.json"]),
        task_from(data["task.json"]),
    )
    case = CaseSpec(**data["fault.json"])
    if inject(scene, case).content_hash != current.content_hash:
        raise ValueError("FAULT_REPRODUCTION_MISMATCH")
    previous = data["result.json"]
    view = scene if previous["stale_view"] else current
    original = plan_from(data["plan.json"])
    strategy = previous.get("navigation_strategy")
    if original.planner_name == "strategy_astar":
        from worldguard.planners.strategy_astar import Strategy, StrategyAStar
        if not isinstance(strategy, dict) or strategy.get("planner") != "strategy_astar":
            raise ValueError("REPLAY_STRATEGY_MISSING")
        planner = StrategyAStar(Strategy(strategy["turn_cost_m"], strategy["clearance_weight"]))
    elif original.planner_name == ReferenceAStar.name and not strategy:
        planner = ReferenceAStar()
    else:
        raise ValueError("REPLAY_PLANNER_UNSUPPORTED")
    plan = planner.plan(view, task)
    new_audit = audit_path(current, task, plan.path)
    matches = digest(stable_plan(plan)) == digest(stable_plan(original)) and canonical(
        new_audit
    ) == canonical(data["audit.json"])
    recovery_matches = None
    if previous["recovery_plan"] is not None:
        recovery = planner.plan(current, task)
        recovery_matches = digest(stable_plan(recovery)) == digest(
            stable_plan(previous["recovery_plan"])
        ) and canonical(audit_path(current, task, recovery.path)) == canonical(previous["recovery_audit"])
        matches = matches and recovery_matches
    output = {
        "runtime_mode": "REPLAY",
        "source_run_id": previous["run_id"],
        "matches": matches,
        "audit": new_audit,
        "recovery_matches": recovery_matches,
        "model_requests": 0,
    }
    # Never overwrite source evidence, even if a caller passes an internal destination.
    if out.resolve() == case_dir.resolve() or case_dir.resolve() in out.resolve().parents:
        raise ValueError("REPLAY_OUTPUT_INSIDE_SOURCE")
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "replay.json", output)
    return output
