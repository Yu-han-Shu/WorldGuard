"""Direction-aware A* with explicit turn and clearance costs. Safety uses planner geometry only."""

import heapq
import math
import time
from dataclasses import dataclass

from worldguard.contracts import PlanResult, finite
from worldguard.planners.reference_astar import edge_clear


@dataclass(frozen=True)
class Strategy:
    turn_cost_m: float = 0.0
    clearance_weight: float = 0.0

    def __post_init__(self):
        for value in (self.turn_cost_m, self.clearance_weight):
            if not 0 <= finite(value) <= 5:
                raise ValueError("INVALID_STRATEGY")


class StrategyAStar:
    name = "strategy_astar"

    def __init__(self, strategy):
        self.strategy = strategy

    def plan(self, scene, task, *, cancel=None, timeout=10):
        started = time.monotonic()
        blocked = set(scene.occupied) | set(scene.unknown)

        def result(code, path=()):
            return PlanResult(self.name, "strategy-astar-1", scene.content_hash, tuple(path), code,
                              time.monotonic() - started, math.dist(path[-1], task.goal_xy_m) if path else None)

        if scene.scene_id != task.scene_id:
            return result("SCENE_MISMATCH")
        start, goal = task.start_xy_m, task.goal_xy_m
        if not edge_clear(scene, task.robot, start, start):
            return result("START_BLOCKED")
        if not edge_clear(scene, task.robot, goal, goal):
            return result("GOAL_BLOCKED")
        if start == goal:
            return result("PLANNED", [start])
        source, target = scene.world_to_cell(start), scene.world_to_cell(goal)
        center = scene.cell_center
        if not edge_clear(scene, task.robot, start, center(source)) or not edge_clear(
                scene, task.robot, center(target), goal):
            return result("ENDPOINT_CONNECTION_BLOCKED")
        origin = (*source, -1)
        queue, cost, previous = [(0, 0, origin)], {origin: 0}, {}
        safe, clearances = {}, {}

        def clearance(cell):
            if cell not in clearances:
                x, y = center(cell)
                ox, oy = scene.origin_xy_m
                res = scene.resolution_m
                distance = min(x - ox, y - oy, ox + scene.width * res - x, oy + scene.height * res - y)
                for row, col in (*scene.occupied, *scene.unknown):
                    left, bottom = ox + col * res, oy + row * res
                    distance = min(distance, math.hypot(max(left - x, x - left - res, 0),
                                                       max(bottom - y, y - bottom - res, 0)))
                clearances[cell] = distance - task.robot.effective_radius
            return clearances[cell]

        while queue:
            if cancel is not None and cancel.is_set():
                return result("CANCELLED")
            if time.monotonic() - started >= timeout:
                return result("PLANNER_TIMEOUT")
            _, actual, node = heapq.heappop(queue)
            if actual != cost[node]:
                continue
            row, col, direction = node
            cell = (row, col)
            if cell == target:
                cells = [cell]
                while node in previous:
                    node = previous[node]
                    cells.append(node[:2])
                points = [start] + [center(c) for c in reversed(cells)] + [goal]
                path = [points[0]]
                for p in points[1:]:
                    if p != path[-1]:
                        path.append(p)
                return result("PLANNED", path)
            for heading, neighbor in enumerate(((row - 1, col), (row + 1, col),
                                                (row, col - 1), (row, col + 1))):
                nr, nc = neighbor
                if not (0 <= nr < scene.height and 0 <= nc < scene.width):
                    continue
                key = tuple(sorted((cell, neighbor)))
                if key not in safe:
                    safe[key] = edge_clear(scene, task.robot, center(cell), center(neighbor), blocked)
                if not safe[key]:
                    continue
                length = scene.resolution_m
                extra = self.strategy.turn_cost_m if direction not in (-1, heading) else 0
                if self.strategy.clearance_weight:
                    extra += self.strategy.clearance_weight * length / (1 + max(0, clearance(neighbor)))
                total = actual + length + extra
                next_node = (nr, nc, heading)
                if total >= cost.get(next_node, float("inf")):
                    continue
                cost[next_node], previous[next_node] = total, node
                heuristic = (abs(nr - target[0]) + abs(nc - target[1])) * length
                heapq.heappush(queue, (total + heuristic, total, next_node))
        return result("NO_PATH")
