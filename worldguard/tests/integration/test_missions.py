"""Goals stay bounded; reports and public decisions cite actual independent evidence."""
import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from worldguard.api import create_app
from worldguard.campaign.runner import CampaignRunner
from worldguard.missions import generate_preview
from worldguard.scene import make_scene


def test_procedural_map_is_reproducible_and_diverse():
    hashes = {make_scene('generated', seed)[0].content_hash for seed in range(20)}
    assert len(hashes) == 20
    for seed in (0, 71, 20261014, 2**31-1):
        first, again = generate_preview(seed), generate_preview(seed)
        assert first['scene_hash'] == again['scene_hash']
        assert first['baseline_audit']['status'] == 'PASS'
        assert first['scene']['content_hash'] == first['scene_hash']


def test_mission_plan_executes_scope_preserves_failures_and_survives_restart(tmp_path, monkeypatch):
    monkeypatch.delenv('WORLDGUARD_LIVE_CONFIG', raising=False)
    app = create_app(tmp_path)
    with TestClient(app) as client:
        preview = client.post('/api/v1/scenes/generate', json={'seed':71}).json()
        plan = client.post('/api/v1/missions/plan', json={'preset':'recovery', 'config_id':preview['config_id'],
            'max_cases':2, 'brief':'比较策略'}).json()
        assert plan['max_cases']==2 and plan['compare_strategies']
        assert plan['scene_hash']==preview['scene_hash']
        body = {'config_id':plan['config_id'],'mission_id':plan['mission_id'],'request_id':'goal_test'}
        created = client.post('/api/v1/runs',json=body)
        assert created.status_code==201, created.text
        rid=created.json()['state']['run_id']
        app.state.service.jobs[rid].result(timeout=60)
        assert client.post('/api/v1/runs',json=body).json()['state']['run_id']==rid
        report=client.get(f'/api/v1/runs/{rid}/report').json()
        assert report['status']=='COMPLETED'
        assert report['planned_cases']==report['executed_cases']==2
        assert report['results'][1]['original_audit']['status']=='FAIL'
        assert report['results'][1]['recovery_audit']['status']=='PASS'
        assert report['optimization_evaluations']==4
        # Without a configured model the chat must report unavailable, never pretend a template is AI.
        answer=client.post(f'/api/v1/runs/{rid}/questions',json={'question':'为什么失败？'})
        assert answer.status_code == 503
        assert answer.json()['error']['code'] == 'CHAT_MODEL_UNAVAILABLE'
        exported=client.get(f'/api/v1/runs/{rid}/export')
        with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
            assert json.loads(archive.read('mission.json'))['mission_id']==plan['mission_id']
            assert json.loads(archive.read('agent_decisions.json'))[0]['source']=='RULE_CONTROLLER'
        bad=client.post('/api/v1/runs',json={**body,'request_id':'tampered','config_id':'corridor_stale'})
        assert bad.status_code==422
    with TestClient(create_app(tmp_path)) as client:
        result=client.get(f'/api/v1/runs/{rid}').json()
        assert result['read_only'] and result['mission']['mission_id']==plan['mission_id']
        assert result['agent_decisions']
        assert client.post('/api/v1/runs',json=body).json()['state']['run_id']==rid


def test_bounded_brief_and_invalid_inputs(tmp_path, monkeypatch):
    monkeypatch.delenv('WORLDGUARD_LIVE_CONFIG', raising=False)
    with TestClient(create_app(tmp_path)) as client:
        plan=client.post('/api/v1/missions/plan',json={'brief':'测试窄通道，最多 10 个案例，要多机器人实机'}).json()
        assert plan['config_id']=='corridor_stale' and plan['max_cases']==5
        assert len(plan['notes'])>=3
        assert plan['interpretation']=='BOUNDED_RULES'
        for seed in (-1,2**31,True):
            response=client.post('/api/v1/scenes/generate',json={'seed':seed})
            assert response.status_code==422
        assert client.post('/api/v1/missions/plan',json={'config_id':'generated_v1_s9999999999_stale'}).status_code!=200


def test_public_decisions_require_owned_evidence(tmp_path):
    runner=CampaignRunner(tmp_path)
    rid=runner.create_campaign('dual_route_stale')['run_id']
    runner.publish_decision(rid,'PLAN','先运行基准，然后测试堵路。','',[],['normal','block_route_1'])
    with pytest.raises(ValueError,match='DECISION_EVIDENCE_REQUIRED'):
        runner.publish_decision(rid,'RECOVERY','重规划','block_route_1',[],[])
    path=runner.run_case(rid,'normal','normal')
    audit=runner.audit_path(rid,'normal',path['path_id'])
    with pytest.raises(ValueError,match='INVALID_DECISION_EVIDENCE'):
        runner.publish_decision(rid,'RECOVERY','重规划','block_route_1',[audit['evidence_id']],[])
    with pytest.raises(ValueError,match='UNKNOWN_CASE'):
        runner.publish_decision(rid,'PLAN','伪造案例','',[],['unknown'])
