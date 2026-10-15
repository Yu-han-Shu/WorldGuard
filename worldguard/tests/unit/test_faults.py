from dataclasses import replace

import pytest

from worldguard.faults import CaseSpec, inject
from worldguard.scene import make_scene


@pytest.mark.parametrize(
    "family,kind",
    [("dual_route", "BLOCK_ROUTE"), ("corridor", "PINCH_CLEARANCE"), ("single_entry", "DISCONNECT_GOAL")],
)
def test_fault_snapshot(family, kind):
    before, task = make_scene(family)
    old_hash, task_hash = before.content_hash, task.task_hash
    spec = CaseSpec("c", old_hash, kind, 11)
    after = inject(before, spec)
    assert inject(before, spec) == after
    assert before.content_hash == old_hash and task.task_hash == task_hash
    assert after.revision == before.revision + 1
    assert set(before.occupied) < set(after.occupied)


def test_reject_faults():
    scene, _ = make_scene()
    with pytest.raises(ValueError):
        CaseSpec("x", scene.content_hash, "BLOCK_ROUTE", 1, 5)
    with pytest.raises(ValueError):
        inject(scene, CaseSpec("x", "wrong", "BLOCK_ROUTE", 1))
    with pytest.raises(ValueError):
        inject(replace(scene, width=33), CaseSpec("x", scene.content_hash, "BLOCK_ROUTE", 1))
