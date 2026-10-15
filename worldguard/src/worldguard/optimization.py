"""Fixed-objective portfolio optimization, independently audited on identical inputs."""

import math
import time
from dataclasses import asdict
from itertools import pairwise

from worldguard.contracts import digest
from worldguard.planners.reference_astar import ReferenceAStar
from worldguard.planners.strategy_astar import Strategy, StrategyAStar
from worldguard.verifier.audit import audit_path

PROFILES = {
    "fewer_turns": Strategy(0.5, 0),
    "clearance": Strategy(0.1, 3),
    "balanced": Strategy(0.25, 1),
}
OBJECTIVE = {"length_weight": 1.0, "turn_cost_m": 0.25, "clearance_cost_m": 1.0}


def evaluate(scene, task, plan):
    audit = audit_path(scene, task, plan.path)
    length = sum(math.dist(a, b) for a, b in pairwise(plan.path))
    directions = []
    for a, b in pairwise(plan.path):
        distance = math.dist(a, b)
        if distance > 0:
            directions.append(((b[0] - a[0]) / distance, (b[1] - a[1]) / distance))
    turns = sum(math.dist(a, b) > 1e-6 for a, b in pairwise(directions))
    clearance = audit["minimum_remaining_clearance_m"]
    valid = plan.code == "PLANNED" and audit["status"] == "PASS"
    score = length + 0.25 * turns + 1 / (1 + max(0, clearance)) if valid else None
    return {"plan": asdict(plan), "audit": audit, "metrics": {"path_length_m": length if valid else None,
            "turns": turns if valid else None, "minimum_remaining_clearance_m": clearance},
            "eligible": valid, "score": score}


def optimize(scene, task, *, cancel=None, timeout=40):
    deadline = time.monotonic() + timeout

    def remaining():
        if cancel is not None and cancel.is_set():
            raise ValueError("OPTIMIZATION_CANCELLED")
        seconds = deadline - time.monotonic()
        if seconds <= 0:
            raise ValueError("OPTIMIZATION_TIMEOUT")
        return min(10, seconds)

    candidates = [{"profile": "baseline", "parameters": None,
                   **evaluate(scene, task, ReferenceAStar().plan(scene, task, cancel=cancel, timeout=remaining()))}]
    for name, strategy in PROFILES.items():
        candidates.append({"profile": name, "parameters": asdict(strategy),
                           **evaluate(scene, task, StrategyAStar(strategy).plan(
                               scene, task, cancel=cancel, timeout=remaining()))})
    eligible = [c for c in candidates if c["eligible"]]
    remaining()
    selected = min(eligible, key=lambda c: c["score"]) if eligible else None
    baseline = candidates[0]
    improved = selected is not None and (not baseline["eligible"] or selected["score"] < baseline["score"] - 1e-9)
    if baseline["eligible"] and not improved:
        selected = baseline
    for candidate in candidates:
        candidate["selection_reason"] = (
            "PLANNING_FAILED" if candidate["plan"]["code"] != "PLANNED" else
            "AUDIT_REJECTED" if not candidate["eligible"] else
            "SELECTED_LOWEST_SCORE" if candidate is selected else "NO_LOWER_SCORE")
    changes = {name: selected["metrics"][name] - baseline["metrics"][name]
               for name in baseline["metrics"]} if selected and baseline["eligible"] else None
    return {"schema_version": "worldguard-optimization/v1", "runtime_mode": "DETERMINISTIC",
            "algorithm": "direction-aware-astar-portfolio", "objective": OBJECTIVE,
            "scene": asdict(scene), "task": asdict(task), "scene_hash": scene.content_hash,
            "task_hash": task.task_hash, "constraints_hash": task.robot.constraints_hash,
            "objective_hash": digest(OBJECTIVE), "planner_evaluations": len(candidates),
            "candidates": candidates, "selected_profile": selected["profile"] if selected else None,
            "decision": "IMPROVED" if improved else "NO_IMPROVEMENT" if selected else "NO_SAFE_PATH",
            "score_improvement": baseline["score"] - selected["score"]
                if selected and baseline["eligible"] else None,
            "metric_changes": changes,
            "selection_reason": "LOWER_FIXED_OBJECTIVE" if improved else
                "BASELINE_RETAINED" if selected else "NO_AUDITED_CANDIDATE",
            "model_requests": 0, "accepted_for_this_case_only": improved}
