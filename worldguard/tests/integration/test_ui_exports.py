import io
import zipfile

from worldguard.campaign.baselines import execute
from worldguard.campaign.runner import CampaignRunner
from worldguard.evidence import read_json
from worldguard.exports import export_run
from worldguard.visuals import scene_svg


def test_map_and_export_real_run(tmp_path):
    runner = CampaignRunner(tmp_path)
    rid = runner.create_campaign("dual_route_stale")["run_id"]
    report = execute(runner, rid)
    case = tmp_path / rid / "cases/block_route_1"
    result = read_json(case / "result.json")
    svg = scene_svg(
        read_json(case / "scene_before.json"),
        read_json(case / "scene_after.json"),
        read_json(case / "task.json"),
        result["original_plan"],
        result["recovery_plan"],
        result["original_audit"],
    )
    assert "<polyline" in svg and "<circle" in svg and "script" not in svg
    (tmp_path / rid / ".env").write_text("DO_NOT_EXPORT")
    payload = export_run(tmp_path, rid)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        assert "report.json" in archive.namelist()
        assert "cases/block_route_1/manifest.json" in archive.namelist()
        assert not any(".." in p or ".env" in p for p in archive.namelist())
        assert b"DO_NOT_EXPORT" not in b"".join(archive.read(n) for n in archive.namelist())
    assert report["results"][1]["original_audit"]["status"] == "FAIL"


def test_workbench_initial_render(monkeypatch):
    from pathlib import Path

    from streamlit.testing.v1 import AppTest

    from worldguard.workbench_client import WorkbenchClient

    monkeypatch.setattr(WorkbenchClient, "request", lambda self, path, *a, **k:
                        {"features": {"live_agnes": False}} if path == "/capabilities" else {"items": []})

    app = AppTest.from_file(str(Path(__file__).resolve().parents[2] / "app.py")).run(timeout=20)
    assert not app.exception
    assert any(button.label == "开始离线测试" for button in app.button)
    assert next(button for button in app.button if button.label == "开始 LIVE Agnes 测试").disabled
