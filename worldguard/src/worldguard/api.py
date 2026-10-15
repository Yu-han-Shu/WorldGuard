"""Local HTTP API for independently developed frontends; generated OpenAPI at /openapi.json."""

import argparse
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from worldguard import __version__
from worldguard.api_models import (
    AuditAction,
    AuditRecord,
    CandidatePage,
    CapabilitiesView,
    CaseAction,
    CaseView,
    ConfigPage,
    CreateRun,
    ErrorResponse,
    EventPage,
    EvidenceQuestion,
    ExperimentView,
    GenerateScene,
    HealthView,
    MissionRequest,
    OptimizationView,
    PassportProbe,
    PassportProbeView,
    PassportView,
    PathRecord,
    RecoverAction,
    ReportView,
    RunPage,
    RunView,
    StopAction,
    StopResult,
    SubmissionRequest,
)
from worldguard.api_service import ApiError, ApiService
from worldguard.campaign.runner import CONFIGS
from worldguard.contracts import identifier
from worldguard.exports import export_run
from worldguard.scene import COMPLEX_FAMILIES, DESCRIPTIONS, complex_layout
from worldguard.visuals import scene_svg

DEFAULT_ORIGINS = [
    f"http://{host}:{port}" for host in ("localhost", "127.0.0.1") for port in (3000, 5173, 8080)
]


def create_app(root=None, *, origins=None):
    root = Path(root or os.environ.get("WORLDGUARD_RUNS_DIR", "artifacts/campaigns"))
    service = ApiService(root)

    @asynccontextmanager
    async def lifespan(_app):
        yield
        service.close()

    app = FastAPI(
        title="WorldGuard Frontend API",
        version="1.0.0",
        description="本地二维导航故障测试接口。LIVE 需后端配置授权；业务核心与 MCP/Streamlit 共用。",
        lifespan=lifespan,
        responses={code: {"model": ErrorResponse} for code in (404, 409, 422, 500, 503)},
    )
    app.state.service = service
    configured = os.environ.get("WORLDGUARD_CORS_ORIGINS")
    allowed = origins if origins is not None else configured.split(",") if configured else DEFAULT_ORIGINS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        expose_headers=["Content-Disposition"],
    )

    @app.exception_handler(ValueError)
    async def business_error(_request: Request, error: ValueError):
        code = error.code if isinstance(error, ApiError) else str(error)
        status = error.status if isinstance(error, ApiError) else 409
        if code == "INVALID_ID":
            status = 422
        elif code.startswith("UNKNOWN_"):
            status = 404
        return JSONResponse(status_code=status, content={"error": {"code": code, "message": code}})

    @app.exception_handler(RequestValidationError)
    async def schema_error(_request: Request, error: RequestValidationError):
        details = [{"loc": list(e["loc"]), "type": e["type"], "message": e["msg"]} for e in error.errors()]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "请求字段或格式不正确",
                    "details": details,
                }
            },
        )

    @app.exception_handler(Exception)
    async def infrastructure_error(_request: Request, _error: Exception):
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INFRASTRUCTURE_ERROR",
                    "message": "服务或证据读取失败；未计为导航算法缺陷",
                }
            },
        )

    @app.get("/api/v1/health", tags=["Configuration"], response_model=HealthView, operation_id="getHealth")
    def health():
        return {
            "status": "ok",
            "api_version": "1.0.0",
            "service_version": __version__,
            "runtime_mode": "DETERMINISTIC",
            "external_model_calls_allowed": service.live is not None,
        }

    @app.get(
        "/api/v1/capabilities",
        tags=["Configuration"],
        response_model=CapabilitiesView,
        operation_id="getCapabilities",
    )
    def capabilities():
        return {
            "agent_provider": getattr(service.live, "config", {}).get("provider", "Agnes") if service.live else "离线规则",
            "runtime_modes": [
                {"id": "DETERMINISTIC", "available": True},
                {"id": "LIVE_AGNES", "available": service.live is not None,
                 "reason": None if service.live is not None else "LIVE_NOT_AVAILABLE"},
            ],
            "testers": ["FixedCoverage", "SeededRandom", "AdaptiveRule"] + (["AgnesAGH"] if service.live else []),
            "navigation_adapters": [
                {"id": "reference_safe_astar", "available": True},
                {"id": "legacy", "available": False, "reason": "SOURCE_NOT_CONFIGURED"},
            ],
            "recovery_actions": ["REFRESH_MAP_REPLAN", "RETRY_TRANSIENT_ONCE", "SAFE_STOP"],
            "features": {
                "automatic": True,
                "manual": True,
                "cancel": True,
                "event_polling": True,
                "export_zip": True,
                "svg_map": True,
                "historical_read": True,
                "resume_writes_after_restart": False,
                "sse": False,
                "live_agnes": service.live is not None,
                "strategy_optimization": True,
                "agent_strategy_optimization": service.live is not None,
                "model_chat": getattr(service.live, "config", {}).get("provider") == "Kimi",
            },
            "geometry": {
                "dimension": 2,
                "units": "meters",
                "cell_order": "row,col",
                "world_axes": "x-right,y-up",
                "unknown_cells": "blocked",
            },
        }

    @app.get("/api/v1/configs", tags=["Configuration"], response_model=ConfigPage, operation_id="listConfigs")
    def configs():
        return {"items": [{"config_id": cid, **config, "description": DESCRIPTIONS[config["family"]],
                           "width_cells": complex_layout(config["family"], config["seed"])[0]
                           if config["family"] in COMPLEX_FAMILIES else 32,
                           "height_cells": complex_layout(config["family"], config["seed"])[1]
                           if config["family"] in COMPLEX_FAMILIES else 24}
                          for cid, config in CONFIGS.items()]}

    @app.post("/api/v1/submissions", tags=["Configuration"], operation_id="receiveSubmission")
    def submission(body: SubmissionRequest):
        from worldguard.submissions import receive_submission
        return receive_submission(service.root, body)

    @app.post(
        "/api/v1/runs", tags=["Runs"], response_model=RunView, status_code=201, operation_id="createRun"
    )
    def create_run(body: CreateRun):
        return service.create(body)

    @app.post("/api/v1/missions/plan", tags=["Missions"], operation_id="prepareMission")
    def prepare_mission(body: MissionRequest):
        from worldguard.missions import prepare_mission
        return prepare_mission(service.root, body)

    @app.post("/api/v1/scenes/generate", tags=["Missions"], operation_id="generateScene")
    def generate_scene(body: GenerateScene):
        from worldguard.missions import generate_preview
        return generate_preview(body.seed, body.version)

    @app.post("/api/v1/runs/{run_id}/questions", tags=["Evidence"], operation_id="askEvidence")
    def ask_evidence(run_id: str, body: EvidenceQuestion):
        from worldguard.evidence_chat import ask
        return ask(service, run_id, body)

    @app.get("/api/v1/runs/{run_id}/questions", tags=["Evidence"], operation_id="getEvidenceChat")
    def evidence_chat(run_id: str):
        from worldguard.evidence_chat import history
        return history(service, run_id)

    @app.get("/api/v1/runs", tags=["Runs"], response_model=RunPage, operation_id="listRuns")
    def list_runs(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
        folders = [
            p
            for p in service.root.glob("run_*")
            if p.is_dir() and not p.is_symlink() and (p / "state.json").is_file()
        ]
        folders.sort(key=lambda p: p.stat().st_mtime_ns, reverse=True)
        return {
            "items": [service.view(p.name) for p in folders[offset : offset + limit]],
            "offset": offset,
            "limit": limit,
            "total": len(folders),
        }

    @app.get("/api/v1/runs/{run_id}", tags=["Runs"], response_model=RunView, operation_id="getRun")
    def get_run(run_id: str):
        return service.view(run_id)

    @app.get("/api/v1/runs/{run_id}/agh", tags=["Evidence"], operation_id="getAghSession")
    def agh_session(run_id: str):
        value = service.view(run_id)["agh_session"]
        if value is None:
            raise ApiError("AGH_EVIDENCE_NOT_READY")
        return value

    @app.post("/api/v1/runs/{run_id}/stop", tags=["Runs"], response_model=RunView, operation_id="stopRun")
    def stop(run_id: str, body: StopAction):
        return service.stop(run_id, body.reason)

    @app.post(
        "/api/v1/runs/{run_id}/finish", tags=["Runs"], response_model=ReportView, operation_id="finishRun"
    )
    def finish(run_id: str):
        return service.action(run_id, service.runner.finish_campaign)

    @app.get(
        "/api/v1/runs/{run_id}/candidates",
        tags=["Cases"],
        response_model=CandidatePage,
        operation_id="listCandidates",
    )
    def candidates(run_id: str):
        return {
            "run_id": run_id,
            "items": [c["candidate"] for c in service.snapshot(run_id)["cases"].values()],
        }

    @app.get(
        "/api/v1/runs/{run_id}/cases/{case_id}",
        tags=["Cases"],
        response_model=CaseView,
        operation_id="getCase",
    )
    def case(run_id: str, case_id: str):
        return service.case(run_id, case_id)

    @app.get(
        "/api/v1/runs/{run_id}/cases/{case_id}/map.svg",
        tags=["Cases"],
        response_class=Response,
        operation_id="getCaseMap",
        responses={200: {"content": {"image/svg+xml": {"schema": {"type": "string"}}}}},
    )
    def map_svg(run_id: str, case_id: str):
        value = service.case(run_id, case_id)
        original = next((p for p in value["paths"] if p["role"] == "original"), None)
        recovery = next((p for p in reversed(value["paths"]) if p["role"] == "recovery"), None)
        before = {k: v for k, v in value["scene_before"].items() if k != "content_hash"}
        after = {k: v for k, v in value["scene_after"].items() if k != "content_hash"}
        svg = scene_svg(
            before,
            after,
            value["task"],
            original["plan"] if original else None,
            recovery["plan"] if recovery else None,
            original["audit"]["audit"] if original and original.get("audit") else None,
        )
        return Response(svg, media_type="image/svg+xml")

    @app.post(
        "/api/v1/runs/{run_id}/cases/{case_id}/run",
        tags=["Actions"],
        response_model=PathRecord,
        operation_id="runCase",
    )
    def run_case(run_id: str, case_id: str, body: CaseAction):
        return service.action(run_id, service.runner.run_case, case_id, body.request_id)

    @app.post("/api/v1/runs/{run_id}/cases/{case_id}/optimize", tags=["Optimization"],
              operation_id="optimizeCase", response_model=OptimizationView)
    def optimize_case(run_id: str, case_id: str):
        return service.optimization(run_id, case_id, create=True)

    @app.get("/api/v1/runs/{run_id}/cases/{case_id}/optimization", tags=["Optimization"],
             operation_id="getOptimization", response_model=OptimizationView)
    def optimization(run_id: str, case_id: str):
        return service.optimization(run_id, case_id)

    @app.get("/api/v1/runs/{run_id}/cases/{case_id}/experiment", tags=["Experiments"],
             operation_id="getCounterfactualExperiment", response_model=ExperimentView)
    def get_experiment(run_id: str, case_id: str):
        from worldguard.experiment_lab import experiment
        return experiment(service, run_id, case_id)

    @app.post("/api/v1/runs/{run_id}/cases/{case_id}/experiment", tags=["Experiments"],
              operation_id="createCounterfactualExperiment", response_model=ExperimentView)
    def create_experiment(run_id: str, case_id: str):
        from worldguard.experiment_lab import experiment
        return experiment(service, run_id, case_id, create=True)

    @app.get("/api/v1/runs/{run_id}/cases/{case_id}/passport", tags=["Evidence"],
             operation_id="getEvidencePassport", response_model=PassportView)
    def evidence_passport(run_id: str, case_id: str, path_id: str | None = None):
        from worldguard.experiment_lab import passport
        return passport(service.case(run_id, case_id), path_id)

    @app.post("/api/v1/runs/{run_id}/cases/{case_id}/passport/probe", tags=["Evidence"],
              operation_id="probeEvidencePassport", response_model=PassportProbeView)
    def passport_probe(run_id: str, case_id: str, body: PassportProbe):
        from worldguard.experiment_lab import probe_passport
        return probe_passport(service.case(run_id, case_id), body.path_id, body.change)

    @app.post(
        "/api/v1/runs/{run_id}/cases/{case_id}/rerun",
        tags=["Actions"],
        response_model=PathRecord,
        operation_id="rerunCase",
    )
    def rerun(run_id: str, case_id: str, body: CaseAction):
        return service.action(run_id, service.runner.run_case, case_id, body.request_id, True)

    @app.post(
        "/api/v1/runs/{run_id}/cases/{case_id}/audit",
        tags=["Actions"],
        response_model=AuditRecord,
        operation_id="auditPath",
    )
    def audit(run_id: str, case_id: str, body: AuditAction):
        return service.action(run_id, service.runner.audit_path, case_id, body.path_id)

    @app.post(
        "/api/v1/runs/{run_id}/cases/{case_id}/recover",
        tags=["Actions"],
        response_model=PathRecord | StopResult,
        operation_id="recoverCase",
    )
    def recover(run_id: str, case_id: str, body: RecoverAction):
        return service.action(
            run_id, service.runner.recover_case, case_id, body.action, body.evidence_ids, body.request_id
        )

    @app.get(
        "/api/v1/runs/{run_id}/events", tags=["Evidence"], response_model=EventPage, operation_id="getEvents"
    )
    def events(run_id: str, cursor: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500)):
        return service.events(run_id, cursor, limit)

    @app.get("/api/v1/runs/{run_id}/evidence/{evidence_id}", tags=["Evidence"], operation_id="getEvidence")
    def evidence(run_id: str, evidence_id: str):
        return service.evidence(run_id, evidence_id)

    @app.get(
        "/api/v1/runs/{run_id}/report", tags=["Evidence"], response_model=ReportView, operation_id="getReport"
    )
    def report(run_id: str):
        return service.report(run_id)

    @app.get(
        "/api/v1/runs/{run_id}/report.md",
        tags=["Evidence"],
        response_class=Response,
        operation_id="downloadReport",
        responses={200: {"content": {"text/markdown": {"schema": {"type": "string"}}}}},
    )
    def report_markdown(run_id: str):
        service.report(run_id)
        payload = (service.folder(run_id) / "report.md").read_bytes()
        return Response(
            payload,
            media_type="text/markdown",
            headers={
                "Content-Disposition": f'attachment; filename="{run_id}.md"',
            },
        )

    @app.get(
        "/api/v1/runs/{run_id}/export",
        tags=["Evidence"],
        response_class=Response,
        operation_id="exportRun",
        responses={200: {"content": {"application/zip": {"schema": {"type": "string", "format": "binary"}}}}},
    )
    def export(run_id: str):
        identifier(run_id)
        service.report(run_id)
        return Response(
            export_run(service.root, run_id),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{run_id}.zip"',
            },
        )

    return app


def main():
    import uvicorn

    parser = argparse.ArgumentParser(description="WorldGuard local frontend HTTP API")
    parser.add_argument("--port", type=int, default=8520)
    parser.add_argument("--runs-dir", default="artifacts/campaigns")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be in 1024..65535")
    uvicorn.run(create_app(args.runs_dir), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
