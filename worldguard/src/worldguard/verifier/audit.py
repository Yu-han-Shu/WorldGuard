import math
from itertools import pairwise

from worldguard.contracts import EPSILON_M, digest, point
from worldguard.verifier.geometry import segment_clearance

VERSION = "capsule-raw-grid-1"


def bindings(scene, task, path):
    return {
        "environment_hash": scene.content_hash,
        "task_hash": task.task_hash,
        "constraints_hash": task.robot.constraints_hash,
        "path_hash": digest(path),
        "verifier_version": VERSION,
    }


def audit_path(scene, task, path):
    result = {
        "status": "UNKNOWN",
        "code": "INVALID_PATH",
        "scene_revision": scene.revision,
        "binding": None,
        "violations": [],
        "epsilon_m": EPSILON_M,
        "start_error_m": None,
        "goal_error_m": None,
        "minimum_centerline_distance_m": None,
        "minimum_remaining_clearance_m": None,
        "certificate_hash": None,
    }
    try:
        if not isinstance(path, (list, tuple)) or not path or len(path) > 100000:
            return result
        points = tuple(point(p) for p in path)
    except (ValueError, TypeError, OverflowError):
        return result
    result["binding"] = bindings(scene, task, points)
    if scene.scene_id != task.scene_id:
        result["code"] = "SCENE_MISMATCH"
        return result
    result["start_error_m"] = math.dist(points[0], task.start_xy_m)
    result["goal_error_m"] = math.dist(points[-1], task.goal_xy_m)
    violations = []
    if result["start_error_m"] > task.robot.endpoint_tolerance_m:
        violations.append({"code": "START_MISMATCH"})
    if result["goal_error_m"] > task.robot.endpoint_tolerance_m:
        violations.append({"code": "GOAL_MISMATCH"})
    distances = []
    segments = list(pairwise(points)) if len(points) > 1 else [(points[0], points[0])]
    for index, (a, b) in enumerate(segments):
        clearance = segment_clearance(scene, a, b)
        distance = clearance["centerline_distance_m"]
        distances.append(distance)
        if distance <= task.robot.effective_radius + EPSILON_M:
            violations.append(
                {
                    "code": "FOOTPRINT_COLLISION",
                    "segment_index": index,
                    "segment_xy_m": (a, b),
                    **clearance,
                    "remaining_clearance_m": distance - task.robot.effective_radius,
                }
            )
    result.update(
        status="FAIL" if violations else "PASS",
        code="VIOLATIONS" if violations else "VERIFIED",
        violations=violations,
        minimum_centerline_distance_m=min(distances),
        minimum_remaining_clearance_m=min(distances) - task.robot.effective_radius,
    )
    if not violations:
        result["certificate_hash"] = digest(result["binding"])
    return result


def validate_certificate(certificate, scene, task, path):
    try:
        expected = bindings(scene, task, tuple(point(p) for p in path))
        if (
            certificate.get("status") == "PASS"
            and certificate.get("binding") == expected
            and certificate.get("certificate_hash") == digest(expected)
        ):
            return "VALID"
    except (ValueError, TypeError):
        pass
    return "STALE_CERTIFICATE"
