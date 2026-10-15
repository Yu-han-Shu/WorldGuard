"""Bounded counterfactual experiments on frozen cases, separate from campaign scores."""

import datetime
import math
import time
from dataclasses import asdict, replace
from itertools import pairwise

from worldguard.contracts import digest, identifier, plan_from, scene_from, task_from
from worldguard.evidence import read_json, write_json
from worldguard.optimization import evaluate
from worldguard.planners.reference_astar import ReferenceAStar
from worldguard.planners.strategy_astar import Strategy, StrategyAStar
from worldguard.verifier.audit import audit_path, bindings, validate_certificate


def inputs(case):
    return (
        scene_from({k: v for k, v in case["scene_after"].items() if k != "content_hash"}),
        task_from(case["task"]),
    )


def passport(case, path_id=None):
    """Recheck saved evidence against current frozen inputs, without rewriting it."""
    from worldguard.api_service import ApiError

    scene, task = inputs(case)
    record = next((p for p in reversed(case["paths"])
                   if (p["path_id"] == path_id if path_id else p.get("audit_status") == "PASS")), None)
    if not record or not record.get("audit"):
        raise ApiError("PASSPORT_PATH_NOT_READY", 404)
    path = record["plan"]["path"]
    saved = record["audit"]["audit"]
    checked = audit_path(scene, task, path)
    binding_status = validate_certificate(saved, scene, task, path)
    value = {
        "schema_version": "worldguard-passport/v1", "run_id": case["run_id"],
        "case_id": case["candidate"]["case_id"], "path_id": record["path_id"],
        "role": record["role"], "evidence_id": record["audit"].get("evidence_id"),
        "binding_status": binding_status, "geometry_status": checked["status"],
        "valid": binding_status == "VALID" and checked["status"] == "PASS",
        "binding": saved.get("binding"), "certificate_hash": saved.get("certificate_hash"),
        "audit": checked, "scene": {**asdict(scene), "content_hash": scene.content_hash},
        "task": asdict(task), "plan": record["plan"],
        "scope": "二维圆盘机器人、静态几何、指定路径；内容哈希非数字签名或第三方安全认证。",
    }
    return {**value, "passport_hash": digest(value)}


def probe_passport(case, path_id, change):
    """Perturb a copy only. Invalidation and geometric safety are separate results."""
    from worldguard.api_service import ApiError

    value = passport(case, path_id)
    if not value["valid"]:
        raise ApiError("PASSPORT_NOT_VALID")
    scene, task = inputs(case)
    path = value["plan"]["path"]
    if change == "map":
        # A passing route has free cells. Place one obstacle on its midpoint.
        cell = scene.world_to_cell(path[len(path) // 2])
        scene = replace(scene, revision=scene.revision + 1, occupied=(*scene.occupied, cell))
        description = "在路径中点加入一个障碍网格"
    elif change == "robot":
        task = replace(task, robot=replace(task.robot, radius_m=task.robot.radius_m + 0.1))
        description = "机器人半径增加 0.10 m，其他条件保持不变"
    else:
        raise ApiError("INVALID_PASSPORT_PROBE", 422)
    expected = bindings(scene, task, path)
    saved = {"status": "PASS", "binding": value["binding"], "certificate_hash": value["certificate_hash"]}
    return {
        "schema_version": "worldguard-passport-probe/v1", "source_passport_hash": value["passport_hash"],
        "change": change, "description": description, "sandbox_only": True,
        "binding_status": validate_certificate(saved, scene, task, path),
        "changed_fields": [k for k in expected if expected[k] != value["binding"][k]],
        "audit": audit_path(scene, task, path), "scene": {**asdict(scene), "content_hash": scene.content_hash},
        "task": asdict(task), "plan": value["plan"], "source_unchanged": True,
    }


def run_experiment(case, config):
    from worldguard.api_service import ApiError

    original = next((p for p in case["paths"] if p["role"] == "original" and p.get("audit")), None)
    if original is None:
        raise ApiError("EXPERIMENT_REQUIRES_AUDITED_PATH")
    scene, task = inputs(case)
    plan = plan_from(original["plan"])
    strategy = config.get("navigation_strategy")
    if plan.planner_name == "strategy_astar" and strategy:
        base_parameters = Strategy(strategy["turn_cost_m"], strategy["clearance_weight"])
        base_planner = StrategyAStar(base_parameters)
    elif plan.planner_name == ReferenceAStar.name:
        base_parameters, base_planner = None, ReferenceAStar()
    else:
        raise ApiError("EXPERIMENT_PLANNER_UNSUPPORTED")
    candidate = Strategy(base_parameters.turn_cost_m if base_parameters else 0.25, 3.0)
    started = time.monotonic()

    def branch(key, label, result, parameters, changes, calls):
        evaluation = evaluate(scene, task, result)
        evaluation["metrics"]["path_length_m"] = (
            sum(math.dist(a, b) for a, b in pairwise(result.path)) if result.path else None)
        return {"id": key, "label": label, "parameters": asdict(parameters) if parameters else None,
                "changes": changes, "planner_calls": calls,
                "outcome": "PASS" if evaluation["eligible"] else
                    "REJECTED" if evaluation["audit"]["status"] == "FAIL" else "INCONCLUSIVE",
                **evaluation}

    baseline = branch("original", "保持原方案", plan, base_parameters, [], 0)
    refreshed = branch("refresh", "只更新地图", base_planner.plan(scene, task, timeout=10), base_parameters,
                       ["planner_map"] if plan.planner_scene_hash != scene.content_hash else [], 1)
    changed = []
    if base_parameters is None:
        changed.append("planner_implementation")
    if base_parameters != candidate:
        changed.append("strategy_parameters")
    alternate = branch("clearance", "更新地图 + 净空策略",
                       StrategyAStar(candidate).plan(scene, task, timeout=10), candidate, changed, 1)
    if baseline["eligible"]:
        conclusion = "原始路径已通过；本轮用于比较替代方案，不能据此宣称修复了缺陷。"
    elif refreshed["eligible"]:
        conclusion = "相同导航器更新地图后通过验收，说明地图刷新在这个案例中足以解除原始失败。"
    elif alternate["eligible"]:
        conclusion = "仅更新地图仍未通过；净空候选通过。该结果仅支持本案例中的组合干预。"
    else:
        conclusion = "本轮未得到通过验收的候选；保留失败或未定结果，不能宣称已修复或已证明不可达。"
    value = {
        "schema_version": "worldguard-counterfactual/v1", "run_id": case["run_id"],
        "case_id": case["candidate"]["case_id"], "source_path_id": original["path_id"],
        "source_evidence_id": original["audit"].get("evidence_id"),
        "created_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "runtime_mode": "DETERMINISTIC", "model_requests": 0, "planner_evaluations": 2,
        "elapsed_seconds": time.monotonic() - started,
        "scene": {**asdict(scene), "content_hash": scene.content_hash}, "task": asdict(task),
        "before": case["scene_before"], "source_case_hash": digest(case),
        "controls": {"environment_hash": scene.content_hash, "task_hash": task.task_hash,
                     "constraints_hash": task.robot.constraints_hash},
        "branches": [baseline, refreshed, alternate], "conclusion": conclusion,
        "comparisons": [
            {"from": "original", "to": "refresh", "changed": refreshed["changes"]},
            {"from": "refresh", "to": "clearance", "changed": changed},
        ],
        "limits": ["固定模板的受控实验，非新增模型决策", "额外 2 次规划，独立于原评测预算与得分",
                   "同一真实地图、目标、机器人尺寸和验收器；只改变规划输入或策略",
                   "候选仅在本场景验证，未修改代码，也不代表跨地图改进"],
    }
    return {**value, "experiment_hash": digest(value)}


def experiment(service, rid, cid, *, create=False):
    from worldguard.api_service import ApiError

    with service.lock:
        case = service.case(rid, cid)
        target = service.folder(rid) / "experiments" / (identifier(cid) + ".json")
        if target.parent.is_symlink() or target.is_symlink():
            raise ApiError("EXPERIMENT_STORAGE_INVALID")
        if target.is_file():
            return read_json(target)
        if not create:
            raise ApiError("EXPERIMENT_NOT_READY", 404)
        view = service.view(rid)
        if view["job_active"] or view["state"]["status"] == "RUNNING":
            raise ApiError("EXPERIMENT_WAIT_FOR_COMPLETION")
        value = run_experiment(case, view["state"]["config"])
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        write_json(temporary, value)
        temporary.replace(target)
        return read_json(target)
