from dataclasses import replace

import pytest

from worldguard.contracts import RobotSpec, Scene, Task
from worldguard.verifier.audit import audit_path, validate_certificate


def fixture():
    scene = Scene("test", 0, (0, 0), 1, 8, 5)
    task = Task("task", "test", (1, 2), (7, 2), RobotSpec(0.2, 0.1))
    return scene, task


def test_thin_wall_between_safe_endpoints():
    scene, task = fixture()
    scene = replace(scene, occupied=((2, 4),))
    audit = audit_path(scene, task, [task.start_xy_m, task.goal_xy_m])
    assert audit["status"] == "FAIL"
    assert audit["violations"][0]["segment_index"] == 0


def test_tangent_and_epsilon_policy():
    scene, task = fixture()
    scene = replace(scene, occupied=((1, 4),))
    task = replace(task, start_xy_m=(1, 2.3), goal_xy_m=(7, 2.3))
    assert audit_path(scene, task, [task.start_xy_m, task.goal_xy_m])["status"] == "FAIL"
    task = replace(task, start_xy_m=(1, 2.30001), goal_xy_m=(7, 2.30001))
    assert audit_path(scene, task, [task.start_xy_m, task.goal_xy_m])["status"] == "PASS"


def test_footprint_crosses_empty_map_boundary():
    scene, task = fixture()
    task = replace(task, start_xy_m=(0.1, 1), goal_xy_m=(0.1, 3))
    assert audit_path(scene, task, [task.start_xy_m, task.goal_xy_m])["status"] == "FAIL"


def test_unknown_and_snapped_goal():
    scene, task = fixture()
    assert (
        audit_path(replace(scene, unknown=((2, 4),)), task, [task.start_xy_m, task.goal_xy_m])["status"]
        == "FAIL"
    )
    audit = audit_path(scene, task, [task.start_xy_m, (6.9, 2)])
    assert any(v["code"] == "GOAL_MISMATCH" for v in audit["violations"])


@pytest.mark.parametrize("path", [[], [(float("nan"), 0)], [(1, float("inf"))], [[1]], None])
def test_malformed_unknown(path):
    scene, task = fixture()
    assert audit_path(scene, task, path)["status"] == "UNKNOWN"


def test_single_point_and_duplicates():
    scene, task = fixture()
    assert audit_path(scene, task, [task.start_xy_m])["status"] == "FAIL"
    task = replace(task, goal_xy_m=task.start_xy_m)
    assert audit_path(scene, task, [task.start_xy_m])["status"] == "PASS"
    assert audit_path(scene, task, [task.start_xy_m] * 3)["status"] == "PASS"


def test_certificate_invalidation():
    scene, task = fixture()
    path = [task.start_xy_m, task.goal_xy_m]
    cert = audit_path(scene, task, path)
    assert validate_certificate(cert, scene, task, path) == "VALID"
    assert validate_certificate(cert, replace(scene, revision=1), task, path) == "STALE_CERTIFICATE"
    assert validate_certificate(cert, scene, replace(task, goal_xy_m=(6, 2)), path) == "STALE_CERTIFICATE"
    assert (
        validate_certificate(cert, scene, replace(task, robot=RobotSpec(0.1, 0)), path) == "STALE_CERTIFICATE"
    )
    assert validate_certificate(cert, scene, task, path + [(6, 2)]) == "STALE_CERTIFICATE"


def test_narrow_corridor():
    scene = Scene("narrow", 0, (0, 0), 1, 6, 5, tuple((r, c) for r in (0, 1, 3, 4) for c in range(6)))
    task = Task("t", "narrow", (1, 2.5), (5, 2.5), RobotSpec(0.5, 0))
    assert audit_path(scene, task, [task.start_xy_m, task.goal_xy_m])["status"] == "FAIL"
