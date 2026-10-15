"""Ephemeral authenticated loopback MCP, bound to one existing API campaign."""

import hmac
import socket
import threading
import time

import uvicorn
from mcp.server import MCPServer
from starlette.responses import Response


class BoundMcp:
    def __init__(self, service, run_id, token):
        self.service, self.run_id, self.token = service, run_id, token
        runner = service.runner
        server = MCPServer("worldguard", log_level="ERROR")

        def invoke(method, *args):
            try:
                if self.finish_requested:
                    raise ValueError("CAMPAIGN_FINISH_REQUESTED")
                return method(run_id, *args)
            except (ValueError, RuntimeError) as error:
                return {"execution_status": "ERROR", "error_code": str(error)}
            finally:
                service.persist(run_id)

        def bound(rid):
            if rid != run_id:
                raise ValueError("UNKNOWN_RUN_OR_WRONG_SESSION")

        @server.tool()
        def wg_health(nonce: str) -> dict:
            if not 1 <= len(nonce) <= 128 or not nonce.isalnum():
                raise ValueError("INVALID_NONCE")
            return {"nonce": nonce, "directory_id": "worldguard",
                    "runtime_mode": runner._get(run_id).get("runtime_mode", "DETERMINISTIC")}

        @server.tool()
        def wg_create_campaign(config_id: str) -> dict:
            """Bind to this API run only; cannot create or access another run."""
            if config_id != runner._get(run_id)["config_id"]:
                raise ValueError("CONFIG_NOT_APPROVED")
            return runner._public(runner._get(run_id))

        @server.tool()
        def wg_list_candidates(run_id: str) -> dict:
            bound(run_id)
            return {"candidates": invoke(runner.list_candidates)}

        @server.tool()
        def wg_publish_decision(run_id: str, phase: str, summary: str, case_id: str = "",
                                evidence_ids: list[str] | None = None, case_order: list[str] | None = None) -> dict:
            """Publish a short user-visible action summary (max 320 characters), not private thoughts.

            PLAN lists real candidate IDs. FINDING/RECOVERY require actual evidence IDs.
            This summary never grants safety approval; only independent audits do.
            """
            bound(run_id)
            return invoke(runner.publish_decision, phase, summary, case_id, evidence_ids or [], case_order or [])

        @server.tool()
        def wg_run_case(run_id: str, case_id: str, request_id: str) -> dict:
            bound(run_id)
            return invoke(runner.run_case, case_id, request_id)

        @server.tool()
        def wg_audit_path(run_id: str, case_id: str, path_id: str) -> dict:
            bound(run_id)
            return invoke(runner.audit_path, case_id, path_id)

        @server.tool()
        def wg_recover_case(run_id: str, case_id: str, action: str, evidence_ids: list[str], request_id: str) -> dict:
            bound(run_id)
            return invoke(runner.recover_case, case_id, action, evidence_ids, request_id)

        @server.tool()
        def wg_optimize_case(run_id: str, case_id: str, evidence_id: str, request_id: str) -> dict:
            """After auditing a case, compare four fixed strategies with independent validation.

            Uses four of eight separate optimization evaluations per campaign. Returns metrics
            and evidence; does not replace original/recovery paths or certify navigation arrival.
            """
            bound(run_id)
            return invoke(runner.optimize_case, case_id, evidence_id, request_id)

        @server.tool()
        def wg_rerun_case(run_id: str, case_id: str, request_id: str) -> dict:
            bound(run_id)
            return invoke(runner.run_case, case_id, request_id, True)

        @server.tool()
        def wg_read_evidence(run_id: str, evidence_id: str) -> dict:
            bound(run_id)
            return invoke(runner.read_evidence, evidence_id)

        @server.tool()
        def wg_finish_campaign(run_id: str) -> dict:
            """Ask to finish; final report seals after AGH usage and session evidence are saved."""
            bound(run_id)
            self.finish_requested = True
            return {"run_id": run_id, "finish_requested": True,
                    "results": service.case_summaries(run_id), "runtime_mode": "LIVE_AGNES"}

        @server.tool()
        def wg_stop_campaign(run_id: str, reason: str) -> dict:
            bound(run_id)
            return invoke(runner.stop_campaign, reason)

        app = server.streamable_http_app(stateless_http=True, json_response=True)

        async def authenticated(scope, receive, send):
            if scope["type"] == "http":
                headers = dict(scope["headers"])
                if not hmac.compare_digest(headers.get(b"authorization", b""), f"Bearer {token}".encode()):
                    await Response(status_code=401)(scope, receive, send)
                    return
            await app(scope, receive, send)

        self.finish_requested = False
        self.socket = socket.socket()
        self.socket.bind(("127.0.0.1", 0))
        self.url = f"http://127.0.0.1:{self.socket.getsockname()[1]}/mcp"
        self.server = uvicorn.Server(uvicorn.Config(authenticated, log_level="error", access_log=False))
        self.thread = threading.Thread(target=self.server.run, kwargs={"sockets": [self.socket]}, daemon=True)

    def __enter__(self):
        self.thread.start()
        deadline = time.monotonic() + 10
        while not self.server.started:
            if not self.thread.is_alive() or time.monotonic() >= deadline:
                self.__exit__(None, None, None)
                raise RuntimeError("LOCAL_MCP_START_FAILED")
            time.sleep(0.01)
        return self

    def __exit__(self, *_args):
        self.server.should_exit = True
        if self.thread.is_alive():
            self.thread.join(timeout=10)
        self.socket.close()
