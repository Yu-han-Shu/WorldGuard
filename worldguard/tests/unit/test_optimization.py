import threading

import pytest

from worldguard.contracts import PlanResult
from worldguard.faults import CaseSpec, inject
from worldguard.optimization import optimize
from worldguard.scene import make_scene


def test_fault_case_can_improve_turns_without_relaxing_safety():
    scene, task = make_scene("dual_route")
    case = CaseSpec("block", scene.content_hash, "BLOCK_ROUTE", 11)
    result = optimize(inject(scene, case), task)
    assert result["decision"] == "IMPROVED"
    assert result["selected_profile"] == "fewer_turns"
    baseline = result["candidates"][0]
    selected = next(c for c in result["candidates"] if c["profile"] == result["selected_profile"])
    assert baseline["audit"]["status"] == selected["audit"]["status"] == "PASS"
    assert selected["metrics"]["turns"] < baseline["metrics"]["turns"]


def test_no_safe_path_is_not_reported_as_improvement():
    scene, task = make_scene("single_entry")
    case = CaseSpec("disconnect", scene.content_hash, "DISCONNECT_GOAL", 11)
    result = optimize(inject(scene, case), task)
    assert result["decision"] == "NO_SAFE_PATH"
    assert result["selected_profile"] is None


@pytest.mark.parametrize("family", ["dual_route", "corridor", "single_entry"])
def test_normal_cases_keep_baseline_and_repeat_selection(family):
    scene, task = make_scene(family)
    first, second = optimize(scene, task), optimize(scene, task)
    assert first["decision"] == "NO_IMPROVEMENT"
    assert first["selected_profile"] == second["selected_profile"] == "baseline"
    assert [c["score"] for c in first["candidates"]] == [c["score"] for c in second["candidates"]]
    assert not first["accepted_for_this_case_only"]


def test_unsafe_shortcut_cannot_be_selected(monkeypatch):
    scene, task = make_scene("dual_route")
    scene = inject(scene, CaseSpec("block", scene.content_hash, "BLOCK_ROUTE", 11))
    shortcut = PlanResult("fixture", "1", scene.content_hash,
                          (task.start_xy_m, task.goal_xy_m), "PLANNED", 0, 0)
    monkeypatch.setattr("worldguard.optimization.StrategyAStar.plan", lambda *a, **k: shortcut)
    result = optimize(scene, task)
    assert result["selected_profile"] == "baseline"
    assert all(c["audit"]["status"] == "FAIL" and c["score"] is None
               for c in result["candidates"][1:])


def test_cancelled_optimization_does_not_accept_a_candidate():
    scene, task = make_scene("dual_route")
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(ValueError, match="OPTIMIZATION_CANCELLED"):
        optimize(scene, task, cancel=cancel)
