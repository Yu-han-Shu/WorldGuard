"""The indexed broad phase must preserve the exact conservative edge predicate."""
import random

from worldguard.planners.reference_astar import rectangle_clear
from worldguard.scene import make_scene


def test_indexed_clearance_matches_full_geometry_scan():
    scene, task = make_scene("challenge", 11)
    blocked = set(scene.occupied) | set(scene.unknown)
    rng = random.Random(24)
    for _ in range(500):
        x, y = rng.randrange(scene.width) * .25, rng.randrange(scene.height) * .25
        bounds = (x, y, x + rng.choice((0, .25, 1)), y + rng.choice((0, .25, 1)))
        assert rectangle_clear(scene, task.robot, bounds, blocked) == rectangle_clear(scene, task.robot, bounds)
