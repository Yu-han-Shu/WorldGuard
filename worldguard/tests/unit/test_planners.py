from dataclasses import replace

from worldguard.contracts import RobotSpec, Scene, Task
from worldguard.planners.reference_astar import ReferenceAStar
from worldguard.scene import FAMILIES, make_scene


def test_all_development_families():
    for family in FAMILIES:
        scene, task = make_scene(family)
        result = ReferenceAStar().plan(scene, task)
        assert result.code == "PLANNED"
        assert result.path[0] == task.start_xy_m
        assert result.path[-1] == task.goal_xy_m


def test_goal_occupied_never_snaps():
    scene, task = make_scene()
    scene = replace(scene, occupied=(*scene.occupied, scene.world_to_cell(task.goal_xy_m)))
    result = ReferenceAStar().plan(scene, task)
    assert result.code == "GOAL_BLOCKED" and not result.path


def test_disconnected():
    scene, task = make_scene("single_entry")
    scene = replace(scene, occupied=tuple((r, 16) for r in range(scene.height)))
    assert ReferenceAStar().plan(scene, task).code == "NO_PATH"


def test_no_diagonal_squeeze():
    scene = Scene("corners", 0, (0, 0), 1, 2, 2, ((0, 1), (1, 0)))
    task = Task("t", scene.scene_id, (0.5, 0.5), (1.5, 1.5), RobotSpec(0.1, 0))
    assert ReferenceAStar().plan(scene, task).code == "NO_PATH"


def test_same_endpoint():
    scene, task = make_scene()
    task = replace(task, goal_xy_m=task.start_xy_m)
    result = ReferenceAStar().plan(scene, task)
    assert result.path == (task.start_xy_m,)
