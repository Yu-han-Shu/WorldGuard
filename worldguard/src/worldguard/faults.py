from dataclasses import asdict, dataclass, replace

from worldguard.contracts import digest, identifier

KINDS = ("NONE", "BLOCK_ROUTE", "PINCH_CLEARANCE", "DISCONNECT_GOAL")


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    parent_scene_hash: str
    kind: str
    seed: int
    severity: int = 1

    def __post_init__(self):
        identifier(self.case_id)
        if self.kind not in KINDS or type(self.seed) is not int or not 0 <= self.seed <= 2**31 - 1:
            raise ValueError("INVALID_FAULT")
        if type(self.severity) is not int or not 1 <= self.severity <= 4:
            raise ValueError("INVALID_FAULT_PARAMETER")

    @property
    def fault_hash(self):
        return digest(asdict(self))


def inject(scene, case):
    if scene.content_hash != case.parent_scene_hash:
        raise ValueError("PARENT_HASH_MISMATCH")
    # Only the built-in frozen scene factory's legal regions are supported.
    if scene.revision != 0:
        raise ValueError("FAULT_REGION_UNSUPPORTED")
    family = scene.scene_id.rsplit("_", 1)[0]
    source_seed = int(scene.scene_id.rsplit("_", 1)[1])
    from worldguard.scene import COMPLEX_FAMILIES, FAULT_KINDS, complex_layout, make_scene

    expected, _ = make_scene(family, source_seed)
    if expected.content_hash != scene.content_hash:
        raise ValueError("FAULT_REGION_UNSUPPORTED")
    if case.kind != "NONE" and case.kind != FAULT_KINDS[family]:
        raise ValueError("FAULT_FAMILY_MISMATCH")
    if family in COMPLEX_FAMILIES:
        regions = complex_layout(family, source_seed)[-1]
        if case.kind != "NONE" and case.severity > len(regions):
            raise ValueError("FAULT_REGION_UNSUPPORTED")
        added = regions[case.severity - 1] if case.kind != "NONE" else set()
        return replace(scene, revision=scene.revision + 1, occupied=tuple(set(scene.occupied) | added))
    mid = 15 + source_seed % 3
    added = set()
    if case.kind == "BLOCK_ROUTE":
        added = {(row, mid) for row in range(6, 10)}
    elif case.kind == "DISCONNECT_GOAL":
        added = {(row, mid) for row in range(9, 15)}
    elif case.kind == "PINCH_CLEARANCE":
        # 1..4 remaining cells, centered on task row 11; never changes robot/goal.
        low = 11 - (case.severity - 1) // 2
        opened = range(low, low + case.severity)
        added = {(row, mid + offset) for row in range(8, 16) for offset in (0, 1) if row not in opened}
    return replace(scene, revision=scene.revision + 1, occupied=tuple(set(scene.occupied) | added))
