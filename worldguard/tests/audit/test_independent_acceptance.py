"""Additional analytical expectations, authored separately from production algorithms.

This is a second-pass self-review, NOT an independent human/agent audit.
"""

from dataclasses import replace

import pytest

from worldguard.contracts import RobotSpec, Scene, Task
from worldguard.verifier.audit import audit_path, validate_certificate
from worldguard.verifier.geometry import segment_rectangle_distance


@pytest.mark.parametrize("height,expected", [(0, 1), (0.5, 0.5), (1, 0), (1.5, 0), (2, 0), (3, 1)])
def test_horizontal_crossing_analytic_clearance(height, expected):
    # Segment spans x=0..5, obstacle spans x=2..3, y=1..2.
    # Its distance is exactly max(1-y, y-2, 0), independently of implementation.
    distance, _ = segment_rectangle_distance((0, height), (5, height), (2, 1, 3, 2))
    assert distance == pytest.approx(expected)


def test_offset_non_square_swept_body_not_just_waypoints():
    scene = Scene("offset_audit", 0, (-10, 20), 0.5, 12, 6, ((2, 6),))
    task = Task("t", "offset_audit", (-9, 21.7), (-5, 21.7), RobotSpec(0.21, 0))
    # Obstacle top y=21.5; path 0.2m above it, body radius 0.21m intersects.
    result = audit_path(scene, task, [task.start_xy_m, task.goal_xy_m])
    assert result["status"] == "FAIL"
    assert result["minimum_centerline_distance_m"] == pytest.approx(0.2)


def test_changed_occupied_cell_rejects_prior_certificate():
    scene = Scene("cert", 0, (0, 0), 1, 8, 5)
    task = Task("t", "cert", (1, 2.5), (7, 2.5), RobotSpec(0.2, 0.1))
    path = [task.start_xy_m, task.goal_xy_m]
    cert = audit_path(scene, task, path)
    assert cert["status"] == "PASS"
    changed = replace(scene, occupied=((2, 4),))  # even with unchanged revision
    assert validate_certificate(cert, changed, task, path) == "STALE_CERTIFICATE"
    assert audit_path(changed, task, path)["status"] == "FAIL"
