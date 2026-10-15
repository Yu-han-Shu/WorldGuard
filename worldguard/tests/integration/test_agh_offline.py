"""Synthetic AGH contracts and real local subprocesses; never provider calls."""

import json
import sys
import threading

import pytest

from worldguard.agh_bridge import LiveBlocked, prepare_session, run_live, run_local_process
from worldguard.agh_trace import LOCAL_TOOLS, correlate_business_events, parse_cli_result, summarize_trace
from worldguard.contracts import digest


def ledger(*events):
    return "\n".join(json.dumps({"seq": i + 1, "type": kind, "data": data})
                     for i, (kind, data) in enumerate(events))


def trace(*, nonce="abc123", dispatch=True, tool=None, error=False):
    events = [("request/sent" if dispatch else "request/header",
               {"model": {"route": "fixture", "id": "test"}})]
    events += [
        ("tool/call", {"toolUseId": "t1", "name": tool or next(iter(LOCAL_TOOLS)),
                       "args": {"nonce": "abc123"}}),
        ("tool/result", {"toolUseId": "t1", "isError": error,
                         "content": [{"type": "text", "text": json.dumps({"nonce": nonce})}]}),
    ]
    return ledger(*events)


def summarize(text):
    return summarize_trace(text, expected_route="fixture", expected_model="test", nonce="abc123")


def test_synthetic_nonce_requires_dispatch_and_joined_success():
    result = summarize(trace())
    assert result["nonce_round_trip"]
    assert result["provenance"] == "UNVERIFIED_IMPORT"
    assert result["total_model_requests"] is None
    for text in (trace(dispatch=False), trace(nonce="wrong"), trace(error=True), trace(tool="wg_health")):
        assert not summarize(text)["nonce_round_trip"]
    assert not summarize(trace().replace('"fixture"', '"other"'))["nonce_round_trip"]


def test_missing_duplicate_and_truncated_tool_events():
    lines = trace().splitlines()
    assert "MISSING_TOOL_RESULT" in summarize("\n".join(lines[:2]))["violations"]
    with pytest.raises(ValueError, match="SEQUENCE"):
        summarize("\n".join(lines[1:]))
    with pytest.raises(ValueError, match="UNPAIRED"):
        summarize(trace() + "\n" + lines[-1].replace('"seq": 3', '"seq": 4'))
    with pytest.raises(ValueError, match="SEQUENCE"):
        summarize(trace() + "\n{")


def test_summary_drops_model_prose_and_arbitrary_tool_arguments():
    text = ledger(("assistant/message", {"content": "PRIVATE_REASONING"}),
                  ("tool/call", {"toolUseId": "t1", "name": "read", "args": {"path": "PRIVATE_PATH"}}))
    result = json.dumps(summarize(text))
    assert "PRIVATE" not in result
    assert "UNEXPECTED_TOOL" in result


def test_cli_result_only_accepts_final_record():
    value = {"v": "agnes-cli-result/v1", "sessionId": "s1", "reason": "completed",
             "exitCode": 0, "lastSeq": 4, "text": "not evidence"}
    assert "text" not in parse_cli_result("log line\n" + json.dumps(value))
    for text in ("", "{}", json.dumps(value) + "\nlog after final", json.dumps({**value, "lastSeq": True})):
        with pytest.raises(ValueError, match="INVALID_AGH_RESULT"):
            parse_cli_result(text)


def test_prepare_never_starts_session_or_enables_live(tmp_path, monkeypatch):
    entry = tmp_path / "packages/cli/dist/local/agnes.mjs"
    entry.parent.mkdir(parents=True)
    entry.write_text("// fixture")
    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: pytest.fail("must not spawn"))
    recipe = prepare_session(tmp_path, tmp_path, tmp_path, "fixture", "test")
    assert recipe["executed"] is False
    assert "primary=fixture/test" in recipe["argv"]
    assert not recipe["readiness"]["available"]
    with pytest.raises(ValueError, match="IDENTIFIER"):
        prepare_session(tmp_path, tmp_path, tmp_path, "--evil", "test")
    with pytest.raises(LiveBlocked):
        run_live({"external_model_calls_allowed": True})


def test_real_local_process_timeout_cancel_output_and_exit():
    def run(code, **kwargs):
        return run_local_process([sys.executable, "-c", code], **kwargs)
    assert run("print('ok')")["stdout"].strip() == "ok"
    assert run("raise SystemExit(3)")["exit_code"] == 3
    assert run("import time; time.sleep(30)", timeout_seconds=0.15)["status"] == "TIMEOUT"
    event = threading.Event()
    timer = threading.Timer(0.15, event.set)
    timer.start()
    try:
        assert run("import time; time.sleep(30)", cancel=event)["status"] == "CANCELLED"
    finally:
        timer.join()
    assert run("print('x' * 10000)", max_output_bytes=100)["status"] == "OUTPUT_LIMIT"


def test_timeout_terminates_spawned_child(tmp_path):
    marker = tmp_path / "child-finished"
    child = f"import time,pathlib; time.sleep(1); pathlib.Path({str(marker)!r}).touch()"
    parent = f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{child!r}]); time.sleep(30)"
    result = run_local_process([sys.executable, "-c", parent], timeout_seconds=0.3)
    assert result["status"] == "TIMEOUT"
    threading.Event().wait(1.1)
    assert not marker.exists()


def test_ledger_to_core_requires_matching_run_input_and_output_hashes():
    name = next(local for local, tool in LOCAL_TOOLS.items() if tool == "wg_audit_path")
    args = {"run_id": "run_fixture", "case_id": "normal", "path_id": "path_fixture"}
    payload = {"case_id": "normal", "path_id": "path_fixture", "audit": {"status": "PASS"}}
    text = ledger(("tool/call", {"toolUseId": "t1", "name": name, "args": args}),
                  ("tool/result", {"toolUseId": "t1", "isError": False, "structured": payload}))
    event = {"event_id": "e1", "run_id": "run_fixture", "case_id": "normal", "tool_name": "wg_audit_path",
             "input_hash": digest({"path_id": "path_fixture"}), "output_hash": digest(payload)}
    assert correlate_business_events(text, [event])[0]["product_event_id"] == "e1"
    for changed in ({"run_id": "other"}, {"output_hash": digest({})}, {"input_hash": digest({})}):
        with pytest.raises(ValueError, match="EVENT_MISMATCH"):
            correlate_business_events(text, [{**event, **changed}])
