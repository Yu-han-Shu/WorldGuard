from dataclasses import replace

import pytest

from worldguard.contracts import RobotSpec, Scene, digest
from worldguard.scene import make_scene


def test_hash_and_immutable_snapshot():
    a, _ = make_scene()
    b = replace(a, occupied=(*a.occupied, (0, 0)), revision=1)
    assert a.content_hash == make_scene()[0].content_hash
    assert b.content_hash != a.content_hash
    assert (0, 0) not in a.occupied
    assert digest({"a": 1, "b": 2}) == digest({"b": 2, "a": 1})


def test_non_square_offset_coordinates():
    scene = Scene("offset", 0, (-2, 3), 0.25, 7, 4)
    for row in range(4):
        for col in range(7):
            assert scene.world_to_cell(scene.cell_center((row, col))) == (row, col)
    assert scene.world_to_cell((-2.01, 3)) == (0, -1)


@pytest.mark.parametrize(
    "change",
    [
        {"width": -1},
        {"height": True},
        {"resolution_m": float("nan")},
        {"origin_xy_m": [float("inf"), 0]},
        {"occupied": [(4, 0)]},
    ],
)
def test_invalid_scene(change):
    with pytest.raises(ValueError):
        Scene(
            **(
                {
                    "scene_id": "bad",
                    "revision": 0,
                    "origin_xy_m": (0, 0),
                    "resolution_m": 0.1,
                    "width": 3,
                    "height": 4,
                }
                | change
            )
        )


def test_invalid_robot():
    with pytest.raises(ValueError):
        RobotSpec(radius_m=-1)
