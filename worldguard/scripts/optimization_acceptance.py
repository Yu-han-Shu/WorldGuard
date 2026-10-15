"""Actual HTTP optimization comparison; optional explicitly authorized Agnes smoke run."""

import argparse
import hashlib
import io
import json
import secrets
import time
import urllib.request
import zipfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://127.0.0.1:8520')
    parser.add_argument('--live', action='store_true', help='One real Agnes run; requires authorized local config')
    parser.add_argument('--existing-live', help='Inspect a previous live run without sending model requests')
    args = parser.parse_args()
    output = Path('evidence/batches/OPTIMIZATION')
    output.mkdir(parents=True, exist_ok=True)

    def request(path, body=None, raw=False):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(args.base + '/api/v1' + path, data=data,
                                     headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=60) as response:
            payload = response.read()
        return payload if raw else json.loads(payload)

    def completed_run(config, mode):
        view = request('/runs', {'config_id': config, 'request_id': secrets.token_hex(12),
                                'runtime_mode': mode})
        path = '/runs/' + view['state']['run_id']
        print(json.dumps({'started': view['state']['run_id'], 'mode': mode}), flush=True)
        deadline = time.monotonic() + 220
        while request(path)['job_active']:
            if time.monotonic() > deadline:
                request(path + '/stop', {})
                raise RuntimeError('ACCEPTANCE_TIMEOUT')
            time.sleep(0.5)
        report = request(path + '/report')
        if mode == 'DETERMINISTIC':
            assert report['status'] == 'COMPLETED', request(path).get('execution_error')
        return path, report

    assert request('/capabilities')['features']['strategy_optimization']
    experiments = []
    for family in ('dual_route', 'corridor', 'single_entry'):
        path, report = completed_run(family + '_current', 'DETERMINISTIC')
        for candidate in request(path + '/candidates')['items']:
            cid = candidate['case_id']
            case_path = path + '/cases/' + cid
            value = request(case_path + '/optimize', {})
            assert value == request(case_path + '/optimization')
            assert value == request(case_path + '/optimize', {})
            assert value['model_requests'] == 0 and value['planner_evaluations'] == 4
            if value['selected_profile']:
                selected = next(c for c in value['candidates'] if c['profile'] == value['selected_profile'])
                assert selected['audit']['status'] == 'PASS'
            with (output / (family + '_' + cid + '.json')).open('w', encoding='utf-8', newline='\n') as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2)
                stream.write('\n')
            experiments.append({'family': family, 'case_id': cid, 'decision': value['decision'],
                                'selected_profile': value['selected_profile'],
                                'score_improvement': value['score_improvement']})
        assert request(path + '/report') == report
        with zipfile.ZipFile(io.BytesIO(request(path + '/export', raw=True))) as archive:
            assert any(name.startswith('optimization/') for name in archive.namelist())
    summary = {'status': 'PASS_DETERMINISTIC', 'experiments': experiments, 'live': 'NOT_RUN'}
    if args.live or args.existing_live:
        # Private usage contains only request allocation IDs/counts; never read credentials.
        usage_path = Path('configs/model_usage.local.json')
        before = json.loads(usage_path.read_text(encoding='utf-8'))
        if args.existing_live:
            path = '/runs/' + args.existing_live
            report = request(path + '/report')
        else:
            path, report = completed_run('dual_route_stale', 'LIVE_AGNES')
        session = request(path + '/agh')
        with zipfile.ZipFile(io.BytesIO(request(path + '/export', raw=True))) as archive:
            assert hashlib.sha256(archive.read('agh_session.jsonl')).hexdigest() == session['ledger_sha256']
        assert session['trace']['nonce_round_trip']
        if report['status'] == 'COMPLETED':
            assert report['reached_count'] == report['executed_cases'] == 2
            assert any(r['original_audit']['status'] == 'FAIL' and r['recovery_audit']['status'] == 'PASS'
                       for r in report['results'])
        after = json.loads(usage_path.read_text(encoding='utf-8'))
        assert all(after['allocations'][key] == count for key, count in before['allocations'].items())
        summary['live'] = {'status': report['status'], 'run_id': report['run_id'],
                           'reached_count': report['reached_count'], 'model_requests': report['model_requests'],
                           'nonce_round_trip': True, 'usage_before': before['reserved_requests'],
                           'usage_after': after['reserved_requests'], 'history_preserved': True,
                           'session_reason': session.get('reason'),
                           'execution_error': request(path).get('execution_error'),
                           'inspected_existing_run': bool(args.existing_live)}
        if report['status'] != 'COMPLETED':
            summary['status'] = 'PASS_DETERMINISTIC_LIVE_INCOMPLETE'
    with (output / 'acceptance.json').open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
