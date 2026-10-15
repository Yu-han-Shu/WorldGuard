"""V2 is repeatable, blocks a direct line and still permits verified detours."""
import math

import pytest

from worldguard.missions import generate_preview
from worldguard.planners.strategy_astar import Strategy, StrategyAStar
from worldguard.scene import make_scene
from worldguard.verifier.audit import audit_path


@pytest.mark.parametrize("seed", [0, 19, 2048, 20261014, 2**31-1])
def test_v2_requires_nontrivial_route_without_changing_v1(seed):
    preview = generate_preview(seed, "v2")
    scene, task = make_scene("challenge", seed)
    assert preview["scene_hash"] == scene.content_hash
    assert preview["baseline_audit"]["status"] == "PASS"
    assert audit_path(scene, task, [task.start_xy_m, task.goal_xy_m])["status"] == "FAIL"
    result = StrategyAStar(Strategy(.25, 0)).plan(scene, task)
    assert audit_path(scene, task, result.path)["status"] == "PASS"
    length = sum(math.dist(a,b) for a,b in zip(result.path, result.path[1:]))
    assert length > 1.45 * math.dist(task.start_xy_m, task.goal_xy_m)
    assert generate_preview(seed, "v1")["config_id"] == f"generated_v1_s{seed}_stale"
