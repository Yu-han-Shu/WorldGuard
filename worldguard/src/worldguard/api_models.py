"""Versioned HTTP request/response contracts for a separate frontend."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ID_PATTERN = r"^[A-Za-z0-9_-]{1,80}$"
RuntimeMode = Literal["DETERMINISTIC", "LIVE_AGNES"]
Tester = Literal["FixedCoverage", "SeededRandom", "AdaptiveRule", "AgnesAGH"]
RecoveryAction = Literal["REFRESH_MAP_REPLAN", "RETRY_TRANSIENT_ONCE", "SAFE_STOP"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class CreateRun(StrictModel):
    config_id: str = Field(pattern=ID_PATTERN)
    request_id: str = Field(pattern=ID_PATTERN)
    runtime_mode: RuntimeMode = "DETERMINISTIC"
    execution_mode: Literal["automatic", "manual"] = "automatic"
    tester: Tester = "FixedCoverage"
    seed: int = Field(default=101, ge=0, le=2**31 - 1)
    mission_id: str | None = Field(default=None, pattern=ID_PATTERN)


class MissionRequest(StrictModel):
    preset: Literal["comprehensive", "blockage", "clearance", "recovery"] = "comprehensive"
    config_id: str = Field(default="fulfillment_stale", pattern=ID_PATTERN)
    max_cases: int = Field(default=4, ge=2, le=5)
    brief: str = Field(default="", max_length=1000)
    submission_id: str | None = Field(default=None, pattern=ID_PATTERN)


class SubmissionRequest(StrictModel):
    filename: str = Field(min_length=1, max_length=100, pattern=r"^[\w. -]+\.(json|py)$")
    content: str = Field(min_length=1, max_length=64000)


class GenerateScene(StrictModel):
    seed: int = Field(ge=0, le=2**31 - 1, strict=True)
    version: Literal["v1", "v2"] = "v1"


class EvidenceQuestion(StrictModel):
    question: str = Field(min_length=1, max_length=500)
    request_id: str | None = Field(default=None, pattern=ID_PATTERN)
    case_id: str | None = Field(default=None, pattern=ID_PATTERN)


class CaseAction(StrictModel):
    request_id: str = Field(pattern=ID_PATTERN)


class AuditAction(StrictModel):
    path_id: str = Field(pattern=ID_PATTERN)


class PassportProbe(StrictModel):
    path_id: str = Field(pattern=ID_PATTERN)
    change: Literal["map", "robot"]


class RecoverAction(CaseAction):
    action: RecoveryAction
    evidence_ids: list[str] = Field(min_length=1, max_length=10)


class StopAction(StrictModel):
    reason: Literal["USER_CANCELLED", "BUDGET_EXHAUSTED", "INFRASTRUCTURE_ERROR"] = "USER_CANCELLED"


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Any = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class RunState(BaseModel):
    run_id: str
    status: Literal["RUNNING", "COMPLETED", "BLOCKED", "CANCELLED", "ERROR"]
    runtime_mode: RuntimeMode
    config: dict[str, Any]
    sut_executions: int
    remaining_actions: int
    tool_calls: int
    optimization_evaluations: int = 0
    max_optimization_evaluations: int = 8
    model_requests: int | None
    model_tokens: int | None
    observed_model_tokens: int | None = None
    model_usage_complete: bool | None = None
    model_cost: float | None
    task_hash: str
    constraints_hash: str
    elapsed_seconds: float


class RunView(BaseModel):
    submission: dict[str, Any] | None = None
    mission: dict[str, Any] | None = None
    agent_decisions: list[dict[str, Any]] = Field(default_factory=list)
    execution_error: dict[str, str] | None = None
    state: RunState
    config_id: str | None
    execution_mode: Literal["automatic", "manual", "legacy"]
    tester: str | None
    read_only: bool
    interrupted: bool
    job_active: bool
    report_available: bool
    created_at: str | None
    links: dict[str, str]
    agh_session: dict[str, Any] | None = None


class RunPage(BaseModel):
    items: list[RunView]
    offset: int
    limit: int
    total: int


class Candidate(BaseModel):
    case_id: str
    fault: str
    severity: int


class CandidatePage(BaseModel):
    run_id: str
    items: list[Candidate]


class SceneView(BaseModel):
    scene_id: str
    revision: int
    origin_xy_m: tuple[float, float]
    resolution_m: float
    width: int
    height: int
    occupied: list[tuple[int, int]]
    unknown: list[tuple[int, int]]
    schema_version: str
    source: str
    content_hash: str


class RobotView(BaseModel):
    radius_m: float
    clearance_margin_m: float
    endpoint_tolerance_m: float


class TaskView(BaseModel):
    task_id: str
    scene_id: str
    start_xy_m: tuple[float, float]
    goal_xy_m: tuple[float, float]
    robot: RobotView


class PlanView(BaseModel):
    planner_name: str
    planner_version: str
    planner_scene_hash: str
    path: list[tuple[float, float]]
    code: str
    elapsed_seconds: float
    endpoint_error_m: float | None


class AuditView(BaseModel):
    status: Literal["PASS", "FAIL", "UNKNOWN"]
    code: str
    binding: dict[str, str] | None
    violations: list[dict[str, Any]]
    epsilon_m: float
    scene_revision: int | None = None
    start_error_m: float | None = None
    goal_error_m: float | None = None
    minimum_centerline_distance_m: float | None = None
    minimum_remaining_clearance_m: float | None = None
    certificate_hash: str | None = None


class AuditRecord(BaseModel):
    case_id: str
    path_id: str
    audit: AuditView
    evidence_id: str | None


class OptimizationMetrics(BaseModel):
    path_length_m: float | None
    turns: int | None
    minimum_remaining_clearance_m: float | None


class ExperimentBranch(BaseModel):
    id: str
    label: str
    parameters: dict[str, float] | None
    changes: list[str]
    planner_calls: int
    outcome: Literal["PASS", "REJECTED", "INCONCLUSIVE"]
    plan: PlanView
    audit: AuditView
    metrics: OptimizationMetrics
    eligible: bool
    score: float | None


class ExperimentView(BaseModel):
    schema_version: str
    run_id: str
    case_id: str
    source_path_id: str
    source_evidence_id: str | None
    created_at: str
    runtime_mode: Literal["DETERMINISTIC"]
    model_requests: Literal[0]
    planner_evaluations: int
    elapsed_seconds: float
    scene: SceneView
    before: SceneView
    task: TaskView
    source_case_hash: str
    controls: dict[str, str]
    branches: list[ExperimentBranch]
    comparisons: list[dict[str, Any]]
    conclusion: str
    limits: list[str]
    experiment_hash: str


class PassportView(BaseModel):
    schema_version: str
    run_id: str
    case_id: str
    path_id: str
    role: str
    evidence_id: str | None
    binding_status: str
    geometry_status: str
    valid: bool
    binding: dict[str, str] | None
    certificate_hash: str | None
    audit: AuditView
    scene: SceneView
    task: TaskView
    plan: PlanView
    scope: str
    passport_hash: str


class PassportProbeView(BaseModel):
    schema_version: str
    source_passport_hash: str
    change: str
    description: str
    sandbox_only: bool
    binding_status: str
    changed_fields: list[str]
    audit: AuditView
    scene: SceneView
    task: TaskView
    plan: PlanView
    source_unchanged: bool


class OptimizationCandidate(BaseModel):
    selection_reason: str | None = None
    profile: Literal["baseline", "fewer_turns", "clearance", "balanced"]
    parameters: dict[str, float] | None
    plan: PlanView
    audit: AuditView
    metrics: OptimizationMetrics
    eligible: bool
    score: float | None


class OptimizationView(BaseModel):
    selection_reason: str | None = None
    metric_changes: OptimizationMetrics | None = None
    run_id: str
    case_id: str
    schema_version: Literal["worldguard-optimization/v1"]
    runtime_mode: Literal["DETERMINISTIC"]
    algorithm: str
    objective: dict[str, float]
    scene: dict[str, Any]
    task: TaskView
    scene_hash: str
    task_hash: str
    constraints_hash: str
    objective_hash: str
    planner_evaluations: int
    candidates: list[OptimizationCandidate]
    selected_profile: str | None
    decision: Literal["IMPROVED", "NO_IMPROVEMENT", "NO_SAFE_PATH"]
    score_improvement: float | None
    model_requests: Literal[0]
    accepted_for_this_case_only: bool


class PathRecord(BaseModel):
    case_id: str
    path_id: str
    role: Literal["original", "rerun", "recovery"]
    plan: PlanView
    evidence_id: str | None = None
    audit_status: Literal["NOT_RUN", "PASS", "FAIL", "UNKNOWN"] = "NOT_RUN"
    audit: AuditRecord | None = None


class StopResult(BaseModel):
    case_id: str
    navigation_status: Literal["SAFE_STOP"]
    reached: bool
    reason_code: str


class CaseView(BaseModel):
    run_id: str
    candidate: Candidate
    scene_before: SceneView
    scene_after: SceneView
    task: TaskView
    paths: list[PathRecord]
    stopped: bool
    result: dict[str, Any] | None


class EventView(BaseModel):
    event_id: str
    run_id: str
    case_id: str | None
    timestamp: str
    tool_name: str
    request_id: str | None
    input_hash: str
    output_hash: str
    status: str
    artifact_refs: list[str]
    runtime_mode: RuntimeMode


class EventPage(BaseModel):
    items: list[EventView]
    next_cursor: int
    has_more: bool


class ReportView(RunState):
    optimizations: list[dict[str, Any]] = Field(default_factory=list)
    verdict: Literal["BOUNDED_PASS", "FAILURES_FOUND", "INCONCLUSIVE"]
    results: list[dict[str, Any]]
    planned_cases: int
    executed_cases: int
    reached_count: int
    safe_stop_count: int
    report_path: str
    agh_session: dict[str, Any] | None = None


class HealthView(BaseModel):
    status: Literal["ok"]
    api_version: str
    service_version: str
    runtime_mode: RuntimeMode
    external_model_calls_allowed: bool


class Availability(BaseModel):
    id: str
    available: bool
    reason: str | None = None


class CapabilitiesView(BaseModel):
    agent_provider: str = "Agnes"
    runtime_modes: list[Availability]
    testers: list[Tester]
    navigation_adapters: list[Availability]
    recovery_actions: list[RecoveryAction]
    features: dict[str, bool]
    geometry: dict[str, Any]


class ConfigView(BaseModel):
    config_id: str
    family: Literal["dual_route", "corridor", "single_entry", "warehouse", "office", "switchback",
                    "depot", "campus", "labyrinth", "fulfillment", "sorting", "terminal", "generated", "challenge"]
    description: str = ""
    width_cells: int = 32
    height_cells: int = 24
    stale_view: bool
    seed: int
    max_actions: int
    max_recoveries_per_case: int
    max_seconds: int
    max_tools: int


class ConfigPage(BaseModel):
    items: list[ConfigView]
