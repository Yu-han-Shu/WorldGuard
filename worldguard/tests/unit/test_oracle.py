from dataclasses import replace

from worldguard.contracts import RobotSpec, Scene, Task
from worldguard.verifier.oracle import reachable


def test_analytic_closed_wall_and_open_route():
    scene = Scene("small", 0, (0, 0), 1, 6, 4, tuple((r, 3) for r in range(4)))
    task = Task("t", "small", (1.5, 1.5), (4.5, 1.5), RobotSpec(0.1, 0))
    assert reachable(scene, task)["status"] == "UNREACHABLE"
    assert reachable(replace(scene, occupied=((0, 3),)), task)["status"] == "REACHABLE"


def test_oracle_timeout_unknown():
    scene = Scene("s", 0, (0, 0), 1, 4, 4)
    task = Task("t", "s", (0.5, 0.5), (3.5, 3.5), RobotSpec(0.1, 0))
    assert reachable(scene, task, timeout_seconds=0)["status"] == "UNKNOWN"
