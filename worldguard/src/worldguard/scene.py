"""Self-contained development scene families. Seed affects geometry deterministically."""

import random

from worldguard.contracts import RobotSpec, Scene, Task

LEGACY_FAMILIES = ("dual_route", "corridor", "single_entry")
COMPLEX_FAMILIES = ("warehouse", "office", "switchback", "depot", "campus", "labyrinth",
                    "fulfillment", "sorting", "terminal", "generated", "challenge")
FAMILIES = LEGACY_FAMILIES + COMPLEX_FAMILIES
DEV_SEEDS = (11, 23, 37)
FAULT_KINDS = dict(zip(FAMILIES, ("BLOCK_ROUTE", "PINCH_CLEARANCE", "DISCONNECT_GOAL",
                                "BLOCK_ROUTE", "BLOCK_ROUTE", "DISCONNECT_GOAL",
                                "BLOCK_ROUTE", "BLOCK_ROUTE", "DISCONNECT_GOAL",
                                "BLOCK_ROUTE", "BLOCK_ROUTE", "BLOCK_ROUTE", "BLOCK_ROUTE", "BLOCK_ROUTE")))
DESCRIPTIONS = {
    "challenge": "错位通道仓：四个作业分区、三组双出口隔墙、连续转弯与备用绕行通道",
    "generated": "程序化仓库：种子控制分区、货架尺寸与设备岛，保留主通道及绕行环路",
    "dual_route": "双通道绕行", "corridor": "净空走廊", "single_entry": "单入口目标区",
    "warehouse": "仓库货架：多条横向通道与局部堵路",
    "office": "多房间办公区：多个门口与跨房间绕行",
    "switchback": "折返通道：连续转弯、侧支路与出口断连",
    "depot": "密集物流仓：四列厚货架、双层横向通道与多点堵路",
    "campus": "多区实验园：六个分区、多入口、内部设备岛与联合封门",
    "labyrinth": "长程回廊：四次交替折返、侧支路与关键门口隔断",
    "fulfillment": "立体货架仓：双排十组货架、中央主通道、外围绕行与装卸设备岛",
    "sorting": "交错分拣中心：横向作业带、错位设备岛与多条纵横交叉通道",
    "terminal": "联运装卸站：六个独立作业区、双门连接与分区内设备阵列",
}


def complex_layout(family, seed):
    """Frozen synthetic geometry and its legal fault region, never planner-derived."""
    shift = seed % 5 - 2
    width, height = 40, 32
    upper, lower = 7 + shift, 23 - shift
    occupied = set()
    if family == "challenge":
        # V2 is a separate family: old scene hashes and runs remain reproducible.
        # Alternating primary gates force route decisions; each has a longer bypass.
        rng = random.Random(seed)
        width, height = 88, 64
        gates = [(24, 16 + rng.randint(-2, 2), 6),
                 (44, 46 + rng.randint(-2, 2), 57),
                 (66, 16 + rng.randint(-2, 2), 6)]
        for col, primary, alternate in gates:
            doors = set(range(primary - 2, primary + 3)) | set(range(alternate - 2, alternate + 3))
            occupied.update((r, c) for r in range(height) for c in (col, col + 1) if r not in doors)
        for lo, hi in ((6, 20), (29, 40), (49, 62), (71, 84)):
            for row in (5, 27, 53):
                for col in (lo, hi - 4):
                    tall = rng.randint(4, 7)
                    occupied.update((r, c) for r in range(row, row + tall) for c in range(col, col + 4))
        start, goal = (32, 3), (32, 85)
        faults = [{(r, c) for r in range(primary - 2, primary + 3) for c in (col, col + 1)}
                  for col, primary, _ in gates]
    elif family == "generated":
        # Version 1: a guaranteed open spine plus independently varied rack islands.
        # Obstacles stay outside a five-cell spine; fault regions are geometric, not planner-derived.
        rng = random.Random(seed)
        width, height = rng.choice((80, 86, 92)), rng.choice((60, 64, 68))
        aisle = height // 2 + rng.randint(-2, 2)
        col = 9
        while col < width - 12:
            rack_width = rng.randint(4, 8)
            for lo, hi in ((7, aisle - 4), (aisle + 5, height - 7)):
                split = (lo + hi) // 2 + rng.randint(-2, 2)
                for bottom, top in ((lo, split - 2), (split + 2, hi)):
                    inset = rng.randint(0, 2)
                    occupied.update((r, c) for r in range(bottom, top)
                                    for c in range(col + inset, col + rack_width))
            col += rack_width + rng.randint(4, 7)
        for c in range(7, width - 8, 13):
            length = rng.randint(3, 7)
            occupied.update((r, x) for r in (2, 3) for x in range(c, c + length))
        start, goal = (aisle, 4), (aisle, width - 5)
        faults = [{(r, c) for r in range(aisle - 2, aisle + 3) for c in (x, x + 1)}
                  for x in (width // 4, width // 2, 3 * width // 4)]
    elif family == "fulfillment":
        width, height = 76, 56
        aisle = 27 + shift
        for col in (10, 23, 36, 49, 62):
            for lo, hi in ((7, aisle - 4), (aisle + 5, 49)):
                occupied.update((r, c) for r in range(lo, hi) for c in range(col, col + 7))
        # Staging equipment remains outside the central navigation corridor.
        for col in (6, 29, 52, 68):
            occupied.update((r, c) for r in range(2, 5) for c in range(col, col + 4))
        start, goal = (aisle, 4), (aisle, 72)
        faults = [{(r, c) for r in range(aisle - 3, aisle + 4) for c in range(col, col + 3)}
                  for col in (19, 43, 58)]
    elif family == "sorting":
        width, height = 72, 56
        aisle = 31 + shift
        for row, cols in ((6, (8, 32, 55)), (18, (13, 40)), (40, (6, 30, 54)), (49, (18, 43))):
            for col in cols:
                length = 12 if row in (6, 40) else 17
                occupied.update((r, c) for r in range(row, row + 4)
                                for c in range(col, min(col + length, 68)))
        # Different gate widths are reproducible seed variants of one scene type.
        occupied.update((r, 35 + shift) for r in range(23, 27))
        start, goal = (aisle, 4), (aisle, 67)
        faults = [{(r, c) for r in range(aisle - 3, aisle + 4) for c in range(col, col + 4)}
                  for col in (24, 48)]
        faults.append(faults[0] | faults[1])
    elif family == "terminal":
        width, height = 78, 60
        upper, lower = 14 + shift, 44 - shift
        for col in (26, 52):
            occupied.update((r, c) for r in range(height) for c in (col, col + 1)
                            if r not in range(upper - 2, upper + 3)
                            and r not in range(lower - 2, lower + 3))
        occupied.update((30, c) for c in range(width)
                        if not any(c in range(door - 3, door + 4) for door in (13, 39, 65)))
        for row in (4, 22, 35, 52):
            for col in (5, 16, 31, 42, 57, 68):
                occupied.update((r, c) for r in range(row, row + 4) for c in range(col, col + 5))
        start, goal = (upper, 3), (upper, 74)
        faults = [{(r, c) for r in range(upper - 2, upper + 3) for c in (col, col + 1)}
                  for col in (26, 52)]
        faults.append(faults[0] | faults[1])
    elif family == "depot":
        width, height = 48, 40
        upper, lower = 9 + shift, 30 - shift
        for col in (10, 19, 28, 37):
            occupied.update((r, c) for r in range(2, 38) for c in range(col, col + 3)
                            if r not in range(upper - 2, upper + 3)
                            and r not in range(lower - 2, lower + 3))
        start, goal = (upper, 4), (upper, 44)
        faults = [{(r, c) for r in range(upper - 2, upper + 3) for c in range(col, col + 3)}
                  for col in (10, 19, 28, 37)]
    elif family == "campus":
        width, height = 60, 44
        upper, lower = 10 + shift, 33 - shift
        for col in (20, 40):
            occupied.update((r, col) for r in range(height)
                            if r not in range(upper - 2, upper + 3)
                            and r not in range(lower - 2, lower + 3))
        occupied.update((22, c) for c in range(width)
                        if not any(c in range(door - 2, door + 3) for door in (10, 30, 50)))
        for row in (3, 16, 26, 38):
            for col in (6, 26, 46):
                occupied.update((r, c) for r in range(row, row + 3) for c in range(col, col + 5))
        start, goal = (upper, 4), (upper, 55)
        faults = [{(r, col) for r in range(upper - 2, upper + 3)} for col in (20, 40)]
        faults.append(faults[0] | faults[1])
    elif family == "labyrinth":
        width, height = 56, 40
        upper, lower = 8 + shift, 31 - shift
        gates = ((12, lower), (24, upper), (36, lower), (46, upper))
        for col, door in gates:
            occupied.update((r, col) for r in range(height) if r not in range(door - 2, door + 3))
        for col in (16, 28, 39):
            occupied.update((20, c) for c in range(col, col + 4))
            occupied.update((r, col + 3) for r in range(17, 20))
        start, goal = (upper, 4), (upper, 52)
        faults = [{(r, col) for r in range(door - 2, door + 3)} for col, door in gates]
    elif family == "warehouse":
        for col in (11, 23, 32):
            occupied.update((r, c) for r in range(3, 29) for c in (col, col + 1)
                            if r not in range(upper - 2, upper + 3)
                            and r not in range(lower - 2, lower + 3))
        start, goal = (upper, 4), (upper, 36)
        faults = [{(r, c) for r in range(upper - 2, upper + 3) for c in (col, col + 1)}
                  for col in (11, 23, 32)]
    elif family == "office":
        for col in (13, 26):
            occupied.update((r, col) for r in range(height)
                            if r not in range(upper - 2, upper + 3)
                            and r not in range(lower - 2, lower + 3))
        occupied.update((16, c) for c in range(width)
                        if not any(c in range(door - 2, door + 3) for door in (6, 20, 34)))
        start, goal = (upper, 4), (upper, 35)
        faults = [{(r, col) for r in range(upper - 2, upper + 3)} for col in (13, 26)]
        faults.append(faults[0] | faults[1])
    elif family == "switchback":
        for col, door in ((12, lower), (26, upper)):
            occupied.update((r, col) for r in range(height) if r not in range(door - 2, door + 3))
        occupied.update((16, c) for c in range(16, 23))
        occupied.update((r, 22) for r in range(12, 16))
        start, goal = (upper, 4), (lower, 35)
        faults = [{(r, col) for r in range(door - 2, door + 3)}
                  for col, door in ((12, lower), (26, upper))]
    else:
        raise ValueError("INVALID_SCENE_SPEC")
    return width, height, occupied, start, goal, faults


def make_scene(family="dual_route", seed=11):
    if family not in FAMILIES or type(seed) is not int or not 0 <= seed <= 2**31 - 1:
        raise ValueError("INVALID_SCENE_SPEC")
    if family in COMPLEX_FAMILIES:
        width, height, occupied, start, goal, _ = complex_layout(family, seed)
        scene = Scene(f"{family}_{seed}", 0, (0.0, 0.0), 0.25, width, height, tuple(occupied))
        return scene, Task(f"task_{seed}", scene.scene_id, scene.cell_center(start),
                           scene.cell_center(goal), RobotSpec())
    width, height, res = 32, 24, 0.25
    mid = 15 + seed % 3
    occupied = set()
    if family == "dual_route":
        occupied = {(r, mid) for r in range(3, 21) if r not in range(6, 10) and r not in range(15, 19)}
    elif family == "corridor":
        occupied = {(r, c) for r in range(height) for c in range(width) if r < 8 or r >= 16}
    else:
        occupied = {(r, mid) for r in range(height) if r not in range(9, 15)}
    scene = Scene(f"{family}_{seed}", 0, (0.0, 0.0), res, width, height, tuple(occupied))
    row = 7 if family == "dual_route" else 11
    task = Task(
        f"task_{seed}", scene.scene_id, scene.cell_center((row, 4)), scene.cell_center((row, 27)), RobotSpec()
    )
    return scene, task
