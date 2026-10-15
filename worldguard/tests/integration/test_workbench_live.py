"""UI contract tests use an in-process HTTP server and offline failure fixtures, never a provider."""

from pathlib import Path

from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from worldguard.api import create_app
from worldguard.workbench_client import WorkbenchClient, WorkbenchError

APP = str(Path(__file__).resolve().parents[2] / "app.py")


def test_ui_live_failure_no_offline_fallback_or_duplicate_on_refresh(tmp_path, monkeypatch):
    monkeypatch.delenv("WORLDGUARD_LIVE_CONFIG", raising=False)
    backend = create_app(tmp_path)

    class OfflineFailure:
        def execute(self, service, rid):
            raise RuntimeError("OFFLINE_TEST_ONLY")

    backend.state.service.live = OfflineFailure()
    posts = []
    with TestClient(backend) as http:
        def transport(self, path, payload=None, *, raw=False):
            if payload is not None:
                posts.append((path, payload))
            response = http.request("POST" if payload is not None else "GET", "/api/v1" + path,
                                    **({"json": payload} if payload is not None else {}))
            if response.status_code >= 400:
                raise WorkbenchError(response.json()["error"]["code"])
            return response.content if raw else response.json()

        monkeypatch.setattr(WorkbenchClient, "request", transport)
        app = AppTest.from_file(APP).run(timeout=20)
        assert not app.exception
        live = next(b for b in app.button if b.label == "开始 LIVE Agnes 测试")
        assert not live.disabled
        live.click().run(timeout=20)
        for job in backend.state.service.jobs.values():
            job.result(timeout=5)
        app.run(timeout=20)
        assert not app.exception
        assert len(posts) == 1
        assert posts[0][1]["runtime_mode"] == "LIVE_AGNES"
        assert posts[0][1]["tester"] == "AgnesAGH"
        assert any("未完整完成" in e.value for e in app.error)
        assert any("LIVE_AGNES · ERROR" in heading.value for heading in app.subheader)
        app.run(timeout=20)
        assert len(posts) == 1


def test_lost_create_response_retries_same_id_without_refresh_submission(monkeypatch):
    posts = []

    def transport(self, path, payload=None, **kwargs):
        if payload is not None:
            posts.append(payload)
            raise WorkbenchError("API_UNAVAILABLE")
        return {"features": {"live_agnes": True}} if path == "/capabilities" else {"items": []}

    monkeypatch.setattr(WorkbenchClient, "request", transport)
    app = AppTest.from_file(APP).run(timeout=20)
    next(b for b in app.button if b.label == "开始 LIVE Agnes 测试").click().run(timeout=20)
    app.run(timeout=20)
    assert len(posts) == 1
    next(b for b in app.button if b.label == "开始 LIVE Agnes 测试").click().run(timeout=20)
    assert len(posts) == 2 and posts[0] == posts[1]
    assert not app.exception


def test_backend_disconnected_disables_both_create_buttons(monkeypatch):
    def disconnected(*args, **kwargs):
        raise WorkbenchError("API_UNAVAILABLE")

    monkeypatch.setattr(WorkbenchClient, "request", disconnected)
    app = AppTest.from_file(APP).run(timeout=20)
    assert not app.exception
    assert all(b.disabled for b in app.button if b.label.startswith("开始"))
    assert any("后端未连接" in e.value for e in app.error)
