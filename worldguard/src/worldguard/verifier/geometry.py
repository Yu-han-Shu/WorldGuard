"""Geometry independent of planner inflation and graph search."""

import math


def point_segment_distance(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    norm = dx * dx + dy * dy
    t = 0.0 if norm == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / norm))
    nearest = (a[0] + t * dx, a[1] + t * dy)
    return math.dist(p, nearest), nearest


def point_rectangle_distance(p, rect):
    left, bottom, right, top = rect
    nearest = (max(left, min(right, p[0])), max(bottom, min(top, p[1])))
    return math.dist(p, nearest), nearest


def segment_rectangle_distance(a, b, rect):
    """Exact minimum distance; slab intersection handles parallel and zero-length edges."""
    t_min, t_max = 0.0, 1.0
    intersects = True
    for axis, low, high in ((0, rect[0], rect[2]), (1, rect[1], rect[3])):
        delta = b[axis] - a[axis]
        if delta == 0:
            if a[axis] < low or a[axis] > high:
                intersects = False
                break
        else:
            ta, tb = (low - a[axis]) / delta, (high - a[axis]) / delta
            t_min, t_max = max(t_min, min(ta, tb)), min(t_max, max(ta, tb))
            if t_min > t_max:
                intersects = False
                break
    if intersects:
        return 0.0, (a[0] + t_min * (b[0] - a[0]), a[1] + t_min * (b[1] - a[1]))
    candidates = [point_rectangle_distance(a, rect), point_rectangle_distance(b, rect)]
    for corner in ((rect[0], rect[1]), (rect[0], rect[3]), (rect[2], rect[1]), (rect[2], rect[3])):
        distance, _ = point_segment_distance(corner, a, b)
        candidates.append((distance, corner))
    return min(candidates, key=lambda value: value[0])


def raw_rectangles(scene):
    ox, oy = scene.origin_xy_m
    res = scene.resolution_m
    for row, col in sorted(set(scene.occupied) | set(scene.unknown)):
        yield (row, col), (ox + col * res, oy + row * res, ox + (col + 1) * res, oy + (row + 1) * res)


def segment_clearance(scene, a, b):
    ox, oy = scene.origin_xy_m
    xmax, ymax = ox + scene.width * scene.resolution_m, oy + scene.height * scene.resolution_m
    boundary = min(min(a[0], b[0]) - ox, min(a[1], b[1]) - oy, xmax - max(a[0], b[0]), ymax - max(a[1], b[1]))
    best = {
        "centerline_distance_m": boundary,
        "obstacle_cell": None,
        "obstacle_xy_m": None,
        "kind": "BOUNDARY",
    }
    for cell, rect in raw_rectangles(scene):
        distance, near = segment_rectangle_distance(a, b, rect)
        if distance < best["centerline_distance_m"]:
            best = {
                "centerline_distance_m": distance,
                "obstacle_cell": cell,
                "obstacle_xy_m": near,
                "kind": "OBSTACLE",
            }
    return best
