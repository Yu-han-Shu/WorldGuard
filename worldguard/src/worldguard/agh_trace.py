"""Project only verifiable facts from an official redacted AGH ledger export.

This validates structure and correlation, not the provenance of an imported file.
Synthetic fixtures must never be promoted to LIVE evidence by this module.
"""

import hashlib
import json

from worldguard.contracts import digest

TOOLS = (
    "wg_health", "wg_create_campaign", "wg_list_candidates", "wg_run_case",
    "wg_audit_path", "wg_recover_case", "wg_rerun_case", "wg_read_evidence",
    "wg_finish_campaign", "wg_stop_campaign", "wg_optimize_case", "wg_publish_decision",
)
PREFIX = "mcp_worldguard_" + hashlib.sha256(b"worldguard").hexdigest()[:8] + "_"
LOCAL_TOOLS = {(PREFIX + name)[:64]: name for name in TOOLS}


def parse_cli_result(stdout):
    """The CLI promises a final result line, not an event stream."""
    try:
        result = json.loads(stdout.strip().splitlines()[-1])
        valid = (
            result["v"] == "agnes-cli-result/v1"
            and isinstance(result["sessionId"], str) and bool(result["sessionId"])
            and isinstance(result["reason"], str)
            and type(result["exitCode"]) is int
            and type(result["lastSeq"]) is int and result["lastSeq"] >= 0
        )
    except (ValueError, IndexError, KeyError, TypeError):
        valid = False
    if not valid:
        raise ValueError("INVALID_AGH_RESULT")
    # Deliberately omit generated prose, credits payloads and tickets.
    return {key: result[key] for key in ("sessionId", "reason", "exitCode", "lastSeq")}


def _tool_payload(data):
    if isinstance(data.get("structured"), dict):
        return data["structured"]
    for block in data.get("content", []):
        if isinstance(block, dict) and block.get("type") == "text":
            try:
                value = json.loads(block.get("text", ""))
            except (ValueError, TypeError):
                continue
            if isinstance(value, dict):
                return value
    return {}


def summarize_trace(text, *, expected_route, expected_model, nonce=None):
    """Join calls/results by toolUseId. Never copy arbitrary model text or args."""
    calls, dispatches, violations = {}, [], []
    last_seq = 0
    nonce_matched = False
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            seq, kind, data = row["seq"], row["type"], row["data"]
            if type(seq) is not int or seq != last_seq + 1 or not isinstance(kind, str):
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise ValueError("INVALID_AGH_EVENT_SEQUENCE") from None
        last_seq = seq
        if kind not in {"request/sent", "tool/call", "tool/result"}:
            continue
        if not isinstance(data, dict):
            raise ValueError("INVALID_AGH_EVENT_DATA")  # noqa: TRY004 - malformed ledger contract
        if kind == "request/sent":
            model = data.get("model", {})
            if not isinstance(model, dict):
                raise ValueError("INVALID_AGH_MODEL")
            matches = model.get("route") == expected_route and model.get("id") == expected_model
            dispatches.append({"seq": seq, "expected_model": matches})
            if not matches:
                violations.append("UNEXPECTED_MODEL")
        elif kind == "tool/call":
            tid = data.get("toolUseId")
            if not isinstance(tid, str) or not tid or tid in calls:
                raise ValueError("INVALID_TOOL_CALL_ID")
            tool = LOCAL_TOOLS.get(data.get("name"))
            if tool is None:
                violations.append("UNEXPECTED_TOOL")
            args = data.get("args", {})
            if not isinstance(args, dict):
                raise ValueError("INVALID_TOOL_ARGS")
            calls[tid] = {
                "tool": tool, "call_seq": seq, "result_seq": None, "success": False,
                "nonce_input_matches": nonce is not None and args.get("nonce") == nonce,
                "after_dispatch": bool(dispatches),
            }
        elif kind == "tool/result":
            tid = data.get("toolUseId")
            if not isinstance(tid, str) or tid not in calls or calls[tid]["result_seq"] is not None:
                raise ValueError("UNPAIRED_TOOL_RESULT")
            call = calls[tid]
            payload = _tool_payload(data)
            call["result_seq"] = seq
            call["success"] = (
                not data.get("isError", False)
                and payload.get("execution_status") != "ERROR"
                and not payload.get("error_code")
            )
            if (call["tool"] == "wg_health" and call["nonce_input_matches"]
                    and call["after_dispatch"] and call["success"] and payload.get("nonce") == nonce):
                nonce_matched = True
    if any(call["result_seq"] is None for call in calls.values()):
        violations.append("MISSING_TOOL_RESULT")
    return {
        "schema_version": "worldguard-agh-trace/v1",
        "provenance": "UNVERIFIED_IMPORT",
        "last_seq": last_seq,
        "primary_dispatch_count": len(dispatches),
        "total_model_requests": None,  # Title/auxiliary calls are not all in request/sent.
        "nonce_round_trip": bool(dispatches) and nonce_matched and not violations,
        "violations": sorted(set(violations)),
        "tools": [{key: call[key] for key in ("tool", "call_seq", "result_seq", "success")}
                  for call in calls.values()],
    }


def correlate_business_events(text, events):
    """Bind official tool calls to core events by exact input/output hashes and run ownership."""
    calls, links = {}, []
    for line in text.splitlines():
        row = json.loads(line)
        data = row["data"]
        if row["type"] == "tool/call":
            calls[data["toolUseId"]] = (row["seq"], LOCAL_TOOLS.get(data["name"]), data["args"])
        if row["type"] != "tool/result":
            continue
        seq, tool, args = calls[data["toolUseId"]]
        payload = _tool_payload(data)
        if tool in {"wg_health", "wg_create_campaign", "wg_finish_campaign"}:
            continue  # Health/binding/finish-request are transport facts, not extra core actions.
        if data.get("isError") or payload.get("execution_status") == "ERROR":
            continue
        inputs = {}
        if tool == "wg_publish_decision":
            inputs = {"phase": args["phase"], "summary": args["summary"], "case_id": args.get("case_id", ""),
                      "evidence_ids": args.get("evidence_ids", []), "case_order": args.get("case_order", [])}
        if tool in {"wg_run_case", "wg_rerun_case"}:
            inputs = {"case_id": args["case_id"], "operation": "rerun" if tool == "wg_rerun_case" else "run"}
        elif tool == "wg_audit_path":
            inputs = {"path_id": args["path_id"]}
        elif tool == "wg_recover_case":
            inputs = {key: args[key] for key in ("case_id", "action", "evidence_ids")}
        elif tool == "wg_read_evidence":
            inputs = {"evidence_id": args["evidence_id"]}
        elif tool == "wg_optimize_case":
            inputs = {key: args[key] for key in ("case_id", "evidence_id")}
        elif tool == "wg_stop_campaign":
            inputs = {"reason": args["reason"]}
        value = payload.get("candidates") if tool == "wg_list_candidates" else payload
        matched = [event for event in events if event["tool_name"] == tool
                   and event["run_id"] == args.get("run_id")
                   and event["input_hash"] == digest(inputs) and event["output_hash"] == digest(value)
                   and ("case_id" not in args or event["case_id"] == args["case_id"])]
        if not matched:
            raise ValueError("AGH_CORE_EVENT_MISMATCH")
        links.append({"agh_call_seq": seq, "agh_result_seq": row["seq"],
                      "product_event_id": matched[0]["event_id"], "tool": tool,
                      "input_hash": matched[0]["input_hash"], "output_hash": matched[0]["output_hash"]})
    return links
