"""Immutable, validated SI-unit contracts with canonical content hashes."""

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, fields

SCHEMA_VERSION = "1.0"
EPSILON_M = 1e-9


def canonical(value):
    if hasattr(value, "__dataclass_fields__"):
        value = asdict(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value):
        raise ValueError("INVALID_ID")
    return value


def finite(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError("NON_FINITE_NUMBER")
    return float(value)


def point(value):
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise ValueError("INVALID_POINT")
    return tuple(finite(x) for x in value)


@dataclass(frozen=True)
class Scene:
    scene_id: str
    revision: int
    origin_xy_m: tuple
    resolution_m: float
    width: int
    height: int
    occupied: tuple = ()
    unknown: tuple = ()
    schema_version: str = SCHEMA_VERSION
    source: str = "SYNTHETIC_GEOMETRIC"

    def __post_init__(self):
        identifier(self.scene_id)
        if self.schema_version != SCHEMA_VERSION or self.source != "SYNTHETIC_GEOMETRIC":
            raise ValueError("UNSUPPORTED_SCENE_SCHEMA")
        if type(self.revision) is not int or self.revision < 0:
            raise ValueError("INVALID_REVISION")
        if any(type(v) is not int or not 1 <= v <= 256 for v in (self.width, self.height)):
            raise ValueError("INVALID_DIMENSIONS")
        object.__setattr__(self, "origin_xy_m", point(self.origin_xy_m))
        resolution = finite(self.resolution_m)
        if not 0 < resolution <= 100:
            raise ValueError("INVALID_RESOLUTION")
        object.__setattr__(self, "resolution_m", resolution)
        for name in ("occupied", "unknown"):
            cells = []
            for cell in getattr(self, name):
                if len(cell) != 2 or any(type(v) is not int for v in cell):
                    raise ValueError("INVALID_CELL")
                row, col = cell
                if not (0 <= row < self.height and 0 <= col < self.width):
                    raise ValueError("CELL_OUT_OF_BOUNDS")
                cells.append((row, col))
            object.__setattr__(self, name, tuple(sorted(set(cells))))

    @property
    def content_hash(self):
        return digest(self)

    def cell_center(self, cell):
        row, col = cell
        return (
            self.origin_xy_m[0] + (col + 0.5) * self.resolution_m,
            self.origin_xy_m[1] + (row + 0.5) * self.resolution_m,
        )

    def world_to_cell(self, xy):
        x, y = point(xy)
        return (
            math.floor((y - self.origin_xy_m[1]) / self.resolution_m),
            math.floor((x - self.origin_xy_m[0]) / self.resolution_m),
        )


@dataclass(frozen=True)
class RobotSpec:
    radius_m: float = 0.18
    clearance_margin_m: float = 0.05
    endpoint_tolerance_m: float = 1e-6

    def __post_init__(self):
        for item in fields(self):
            value = finite(getattr(self, item.name))
            if value < 0 or (item.name == "radius_m" and value == 0):
                raise ValueError("INVALID_ROBOT_CONSTRAINT")
            object.__setattr__(self, item.name, value)

    @property
    def constraints_hash(self):
        return digest(self)

    @property
    def effective_radius(self):
        return self.radius_m + self.clearance_margin_m


@dataclass(frozen=True)
class Task:
    task_id: str
    scene_id: str
    start_xy_m: tuple
    goal_xy_m: tuple
    robot: RobotSpec

    def __post_init__(self):
        identifier(self.task_id)
        identifier(self.scene_id)
        object.__setattr__(self, "start_xy_m", point(self.start_xy_m))
        object.__setattr__(self, "goal_xy_m", point(self.goal_xy_m))
        if not isinstance(self.robot, RobotSpec):
            raise TypeError("INVALID_ROBOT")

    @property
    def task_hash(self):
        return digest(self)


@dataclass(frozen=True)
class PlanResult:
    planner_name: str
    planner_version: str
    planner_scene_hash: str
    path: tuple
    code: str
    elapsed_seconds: float
    endpoint_error_m: float | None

    def __post_init__(self):
        object.__setattr__(self, "path", tuple(point(p) for p in self.path))
        if finite(self.elapsed_seconds) < 0:
            raise ValueError("INVALID_TIME")
        if self.endpoint_error_m is not None and finite(self.endpoint_error_m) < 0:
            raise ValueError("INVALID_ENDPOINT_ERROR")

    @property
    def path_hash(self):
        return digest(self.path)


def scene_from(data):
    return Scene(**data)


def task_from(data):
    values = dict(data)
    values["robot"] = RobotSpec(**values["robot"])
    return Task(**values)


def plan_from(data):
    return PlanResult(**data)
