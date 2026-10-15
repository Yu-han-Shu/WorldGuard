"""Conservative 4-connected A*. Does not import the independent verifier.

Each graph edge requires the full adjacent-cell rectangle to have disk clearance.
This over-approximates the swept capsule; narrow feasible continuous routes may be rejected.
No diagonal movement is allowed, hence no corner cutting. Exact endpoints are retained.
"""

import heapq
import math
import time

from worldguard.contracts import EPSILON_M, PlanResult

VERSION = "reference-safe-astar-1"


def rectangle_clear(scene, robot, bounds, blocked=None):
    x0, y0, x1, y1 = bounds
    clearance = robot.effective_radius + EPSILON_M
    ox, oy = scene.origin_xy_m
    if (
        min(
            x0 - ox,
            y0 - oy,
            ox + scene.width * scene.resolution_m - x1,
            oy + scene.height * scene.resolution_m - y1,
        )
        <= clearance
    ):
        return False
    if blocked is None:
        candidates = (*scene.occupied, *scene.unknown)
    else:
        # Only cells whose bounding boxes can intersect the expanded query.
        # Exact distance and the safety threshold below are unchanged.
        res = scene.resolution_m
        candidates = ((r, c)
                      for r in range(math.floor((y0 - clearance - oy) / res) - 1, math.floor((y1 + clearance - oy) / res) + 1)
                      for c in range(math.floor((x0 - clearance - ox) / res) - 1, math.floor((x1 + clearance - ox) / res) + 1)
                      if (r, c) in blocked)
    for row, col in candidates:
        left, bottom = ox + col * scene.resolution_m, oy + row * scene.resolution_m
        dx = max(left - x1, x0 - (left + scene.resolution_m), 0.0)
        dy = max(bottom - y1, y0 - (bottom + scene.resolution_m), 0.0)
        if math.hypot(dx, dy) <= clearance:
            return False
    return True


def edge_clear(scene, robot, a, b, blocked=None):
    return rectangle_clear(scene, robot, (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])), blocked)


class ReferenceAStar:
    name = "reference_safe_astar"

    def plan(self, scene_view, task, *, cancel=None, timeout=10):
        started = time.monotonic()
        blocked = set(scene_view.occupied) | set(scene_view.unknown)

        def result(code, path=()):
            return PlanResult(
                self.name,
                VERSION,
                scene_view.content_hash,
                tuple(path),
                code,
                time.monotonic() - started,
                math.dist(path[-1], task.goal_xy_m) if path else None,
            )

        if task.scene_id != scene_view.scene_id:
            return result("SCENE_MISMATCH")
        start, goal = task.start_xy_m, task.goal_xy_m
        if not edge_clear(scene_view, task.robot, start, start):
            return result("START_BLOCKED")
        if not edge_clear(scene_view, task.robot, goal, goal):
            return result("GOAL_BLOCKED")
        if start == goal:
            return result("PLANNED", [start])
        source, target = scene_view.world_to_cell(start), scene_view.world_to_cell(goal)
        center = scene_view.cell_center
        if not edge_clear(scene_view, task.robot, start, center(source)) or not edge_clear(
            scene_view, task.robot, center(target), goal
        ):
            return result("ENDPOINT_CONNECTION_BLOCKED")
        queue = [(0, source)]
        previous, cost = {}, {source: 0}
        while queue:
            if cancel is not None and cancel.is_set():
                return result("CANCELLED")
            if time.monotonic() - started > timeout:
                return result("PLANNER_TIMEOUT")
            _, cell = heapq.heappop(queue)
            if cell == target:
                cells = [cell]
                while cell in previous:
                    cell = previous[cell]
                    cells.append(cell)
                points = [start] + [center(c) for c in reversed(cells)] + [goal]
                path = [points[0]]
                for p in points[1:]:
                    if p != path[-1]:
                        path.append(p)
                return result("PLANNED", path)
            row, col = cell
            for neighbor in ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)):
                nr, nc = neighbor
                if not (0 <= nr < scene_view.height and 0 <= nc < scene_view.width):
                    continue
                new_cost = cost[cell] + 1
                if new_cost >= cost.get(neighbor, float("inf")):
                    continue
                if not edge_clear(scene_view, task.robot, center(cell), center(neighbor), blocked):
                    continue
                cost[neighbor], previous[neighbor] = new_cost, cell
                heuristic = abs(nr - target[0]) + abs(nc - target[1])
                heapq.heappush(queue, (new_cost + heuristic, neighbor))
        return result("NO_PATH")
