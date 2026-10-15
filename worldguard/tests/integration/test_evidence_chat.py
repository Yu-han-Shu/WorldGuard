"""Offline model fixtures test evidence binding, accounting, persistence, and honest failure."""
import io
import json
import zipfile
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from worldguard.api import create_app
from worldguard.api_service import ApiError
from worldguard.evidence import read_json, write_json
from worldguard.evidence_chat import context


@pytest.fixture
def chat(tmp_path, monkeypatch):
    monkeypatch.delenv("WORLDGUARD_LIVE_CONFIG", raising=False)
    app = create_app(tmp_path)
    with TestClient(app) as client:
        rid = client.post("/api/v1/runs", json={"config_id": "dual_route_stale", "request_id": "fixture"}).json()["state"]["run_id"]
        service = app.state.service
        service.jobs[rid].result(timeout=30)
        reservations = []
        service.live = SimpleNamespace(config={"provider": "Kimi"},
                                       _budget=lambda rid, **kw: reservations.append((rid, kw)))
        yield service, client, rid, reservations


def test_real_answer_contract_idempotency_history_and_export(chat, monkeypatch):
    service, client, rid, reservations = chat
    before = client.get(f"/api/v1/runs/{rid}/report").json()
    _snapshot, citations = context(service, rid, "block_route_1")
    eid = next(e for e, c in citations.items() if c["case_id"] == "block_route_1")
    calls = []

    def model(live, messages, request_id):
        calls.append(messages)
        evidence = json.loads(messages[-1]["content"])["evidence_context"]
        assert evidence["selected_case"] == "block_route_1"
        assert evidence["cases"][0]["paths"][0]["audit_status"] == "FAIL"
        assert evidence["cases"][0]["paths"][-1]["audit_status"] == "PASS"
        assert evidence["cases"][0]["paths"][0]["path_length_m"] > 0
        assert "api_key" not in json.dumps(evidence) and "content" not in evidence["mission"]
        return {"answer": "测试模型回答：原始路线失败，更新地图后恢复通过。", "evidence_ids": [eid],
                "usage": {"total_tokens": 42}}

    monkeypatch.setattr("worldguard.evidence_chat.complete", model)
    endpoint = f"/api/v1/runs/{rid}/questions"
    request = {"question": "为什么失败？", "request_id": "question_1", "case_id": "block_route_1"}
    result = client.post(endpoint, json=request)
    assert result.status_code == 200, result.text
    assert result.json()["source"] == "LIVE_MODEL"
    assert result.json()["citations"] == [citations[eid]]
    assert client.post(endpoint, json=request).json() == result.json()
    assert len(calls) == len(reservations) == 1 and reservations[0][1] == {"reserve_count": 1}
    assert client.post(endpoint, json={**request, "question": "另一个问题"}).status_code == 409
    history = client.get(endpoint).json()["items"]
    assert len(history) == 1 and history[0]["response"] == result.json()
    assert "context_snapshot" not in history[0]
    assert client.get(f"/api/v1/runs/{rid}/report").json() == before
    with zipfile.ZipFile(io.BytesIO(client.get(f"/api/v1/runs/{rid}/export").content)) as archive:
        saved = json.loads(archive.read("evidence_chat.json"))["items"][0]
        assert saved["context_snapshot"]["selected_case"] == "block_route_1"
        assert saved["usage"]["total_tokens"] == 42
    with TestClient(create_app(service.root)) as restarted:
        assert restarted.get(endpoint).json()["items"] == history
        # An already completed request can be recovered without another model connection.
        assert restarted.post(endpoint, json=request).json() == result.json()


@pytest.mark.parametrize("failure,code", [
    ({"answer": "伪造引用", "evidence_ids": ["unowned"]}, "CHAT_INVALID_RESPONSE"),
    ({"answer": "", "evidence_ids": []}, "CHAT_INVALID_RESPONSE"),
    (ApiError("CHAT_TIMEOUT", 504), "CHAT_TIMEOUT"),
    (RuntimeError("private provider diagnostic"), "CHAT_PROVIDER_ERROR"),
])
def test_no_template_fallback_or_raw_error_and_no_retry_billing(chat, monkeypatch, failure, code):
    _service, client, rid, reservations = chat

    def model(*_):
        if isinstance(failure, Exception):
            raise failure
        return failure

    monkeypatch.setattr("worldguard.evidence_chat.complete", model)
    endpoint = f"/api/v1/runs/{rid}/questions"
    request = {"question": "你好", "request_id": "failed_question"}
    response = client.post(endpoint, json=request)
    assert response.status_code in (502, 504)
    assert response.json()["error"]["code"] == code
    assert "private provider" not in response.text
    assert "answer" not in client.get(endpoint).text
    assert client.post(endpoint, json=request).status_code == 409
    assert len(reservations) == 1


def test_chat_bounds_before_spending_and_multi_turn_context(chat, monkeypatch):
    service, client, rid, reservations = chat
    endpoint = f"/api/v1/runs/{rid}/questions"
    assert client.post(endpoint, json={"question": "x", "case_id": "unknown"}).status_code == 404
    assert client.post(endpoint, json={"question": " "}).status_code == 422
    assert client.post(endpoint, json={"question": "x" * 501}).status_code == 422
    service.chat_lock.acquire()
    try:
        assert client.post(endpoint, json={"question": "x"}).status_code == 409
    finally:
        service.chat_lock.release()
    assert not reservations
    captured = []
    monkeypatch.setattr("worldguard.evidence_chat.complete", lambda live, messages, rid:
                        (captured.append(messages) or {"answer": "你好，我可以解释本次评测。", "evidence_ids": []}))
    assert client.post(endpoint, json={"question": "你好"}).status_code == 200
    assert client.post(endpoint, json={"question": "那帮我解释一下"}).status_code == 200
    assert captured[-1][1]["content"] == "你好"
    assert captured[-1][2]["role"] == "assistant"
    path = service.folder(rid) / "evidence_chat.json"
    data = read_json(path)
    data["items"] *= 10
    write_json(path, data)
    assert client.post(endpoint, json={"question": "x"}).json()["error"]["code"] == "CHAT_BUDGET_EXHAUSTED"
    assert len(reservations) == 2
