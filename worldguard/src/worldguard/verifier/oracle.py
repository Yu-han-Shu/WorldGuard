"""Offline evaluation only: exhaustive finite four-neighbor graph reachability.

Never exposed by the campaign candidate catalog. NO_PATH is bounded to this graph,
including exact endpoint-to-containing-cell-center edges, not all continuous curves.
"""

import time
from collections import deque

from worldguard.contracts import EPSILON_M
from worldguard.verifier.geometry import segment_clearance


def reachable(scene, task, timeout_seconds=15):
    start_time = time.monotonic()
    radius = task.robot.effective_radius + EPSILON_M

    def clear(a, b):
        return segment_clearance(scene, a, b)["centerline_distance_m"] > radius

    base = {
        "model": "four_neighbor_cell_centers_exact_endpoint_edges_v1",
        "visited": 0,
        "scope": "finite grid graph only; not arbitrary continuous or physical reachability",
    }
    if scene.scene_id != task.scene_id:
        return {**base, "status": "UNKNOWN", "reason": "SCENE_MISMATCH"}
    start, goal = task.start_xy_m, task.goal_xy_m
    if not clear(start, start) or not clear(goal, goal):
        return {**base, "status": "UNREACHABLE", "reason": "ENDPOINT_BLOCKED"}
    if start == goal:
        return {**base, "status": "REACHABLE", "visited": 1}
    source, target = scene.world_to_cell(start), scene.world_to_cell(goal)
    if not clear(start, scene.cell_center(source)) or not clear(scene.cell_center(target), goal):
        return {**base, "status": "UNREACHABLE", "reason": "ENDPOINT_GRAPH_EDGE_BLOCKED"}
    queue, seen = deque([source]), {source}
    while queue:
        if time.monotonic() - start_time > timeout_seconds:
            return {**base, "status": "UNKNOWN", "reason": "ORACLE_TIMEOUT", "visited": len(seen)}
        cell = queue.popleft()
        if cell == target:
            return {**base, "status": "REACHABLE", "visited": len(seen)}
        row, col = cell
        for neighbor in ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)):
            nr, nc = neighbor
            if neighbor in seen or not (0 <= nr < scene.height and 0 <= nc < scene.width):
                continue
            if clear(scene.cell_center(cell), scene.cell_center(neighbor)):
                seen.add(neighbor)
                queue.append(neighbor)
    return {**base, "status": "UNREACHABLE", "reason": "EXHAUSTIVE_GRAPH_SEARCH", "visited": len(seen)}
