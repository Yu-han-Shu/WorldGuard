"""Official MCP SDK v2 stdio service. stdout belongs exclusively to MCP."""

from pathlib import Path

from mcp.server import MCPServer

from worldguard import __version__
from worldguard.campaign.runner import CampaignRunner

server = MCPServer("worldguard", version=__version__, log_level="WARNING")
runner = CampaignRunner(Path.cwd() / "artifacts" / "campaigns")


def invoke(method, *args):
    try:
        return method(*args)
    except (ValueError, RuntimeError) as error:
        return {"execution_status": "ERROR", "error_code": str(error), "runtime_mode": "DETERMINISTIC"}
    except OSError:
        return {
            "execution_status": "ERROR",
            "error_code": "EVIDENCE_IO_ERROR",
            "runtime_mode": "DETERMINISTIC",
        }


@server.tool()
def wg_health(nonce: str) -> dict:
    """Return a bounded caller nonce without reading files, secrets, or model services."""
    if not 1 <= len(nonce) <= 128 or not nonce.isalnum():
        raise ValueError("INVALID_NONCE")
    return {
        "nonce": nonce,
        "version": __version__,
        "directory_id": "worldguard",
        "runtime_mode": "DETERMINISTIC",
    }


@server.tool()
def wg_create_campaign(config_id: str) -> dict:
    """Create an approved, bounded deterministic campaign; does not enable LIVE mode."""
    return invoke(runner.create_campaign, config_id)


@server.tool()
def wg_list_candidates(run_id: str) -> dict:
    """List finite legal case IDs without future outcomes or oracle labels."""
    return {"candidates": invoke(runner.list_candidates, run_id)}


@server.tool()
def wg_run_case(run_id: str, case_id: str, request_id: str) -> dict:
    """Run exactly one SUT plan. Audit and recovery require separate calls."""
    return invoke(runner.run_case, run_id, case_id, request_id)


@server.tool()
def wg_audit_path(run_id: str, case_id: str, path_id: str) -> dict:
    """Independently audit a issued path ID against the current raw environment."""
    return invoke(runner.audit_path, run_id, case_id, path_id)


@server.tool()
def wg_recover_case(run_id: str, case_id: str, action: str, evidence_ids: list[str], request_id: str) -> dict:
    """Perform one allowed recovery using prior audit evidence. Never certifies its own output."""
    return invoke(runner.recover_case, run_id, case_id, action, evidence_ids, request_id)


@server.tool()
def wg_optimize_case(run_id: str, case_id: str, evidence_id: str, request_id: str) -> dict:
    """Compare four independently audited strategies using issued case audit evidence; bounded to two cases."""
    return invoke(runner.optimize_case, run_id, case_id, evidence_id, request_id)


@server.tool()
def wg_rerun_case(run_id: str, case_id: str, request_id: str) -> dict:
    """Replay the same frozen fault and original planner view, charging one SUT action."""
    return invoke(runner.run_case, run_id, case_id, request_id, True)


@server.tool()
def wg_read_evidence(run_id: str, evidence_id: str) -> dict:
    """Read an issued evidence ID in this server session; never accepts paths."""
    return invoke(runner.read_evidence, run_id, evidence_id)


@server.tool()
def wg_finish_campaign(run_id: str) -> dict:
    """Recompute counts and reports from raw observed results, preserving all failures."""
    return invoke(runner.finish_campaign, run_id)


@server.tool()
def wg_stop_campaign(run_id: str, reason: str) -> dict:
    """Cancel subsequent actions and preserve evidence from work already performed."""
    return invoke(runner.stop_campaign, run_id, reason)


if __name__ == "__main__":
    server.run(transport="stdio")
