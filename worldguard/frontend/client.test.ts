import test from 'node:test';
import assert from 'node:assert/strict';
import { createWorldGuardClient, WorldGuardError } from './client.ts';

// Run against an actual local server: WORLDGUARD_API_URL=http://127.0.0.1:8520 npm test.
test('browser client runs the real backend and downloads its evidence', {
  skip: !process.env.WORLDGUARD_API_URL,
}, async () => {
  const api = createWorldGuardClient(process.env.WORLDGUARD_API_URL);
  assert.equal((await api.health()).status, 'ok');
  const created = await api.createRun({config_id: 'dual_route_stale', request_id: crypto.randomUUID(),
    execution_mode: 'automatic'});
  const id = created.state.run_id;
  let run = created;
  for (let i = 0; i < 100 && run.job_active; i++) {
    await new Promise(resolve => setTimeout(resolve, 50));
    run = await api.getRun(id);
  }
  assert.equal(run.job_active, false);
  assert.equal((await api.report(id)).reached_count, 2);
  const originalReport = await api.report(id);
  const optimization = await api.optimizeCase(id, 'block_route_1');
  assert.equal(optimization.decision, 'IMPROVED');
  assert.equal(optimization.model_requests, 0);
  assert.deepEqual(await api.optimization(id, 'block_route_1'), optimization);
  assert.deepEqual(await api.report(id), originalReport);
  const data = await api.getCase(id, 'block_route_1');
  assert.equal(data.paths[0]?.audit?.audit.status, 'FAIL');
  assert.equal(data.paths.at(-1)?.audit?.audit.status, 'PASS');
  assert.match(await (await fetch(api.mapURL(id, 'block_route_1'))).text(), /polyline/);
  assert.equal((await fetch(api.exportURL(id))).headers.get('content-type'), 'application/zip');
  assert.ok((await api.events(id)).items.length > 0);
  const live = (await api.capabilities()).runtime_modes.find(mode => mode.id === 'LIVE_AGNES');
  if (!live?.available) {
    await assert.rejects(() => api.createRun({config_id: 'dual_route_stale', request_id: crypto.randomUUID(),
      runtime_mode: 'LIVE_AGNES'}), (e: unknown) => e instanceof WorldGuardError && e.code === 'LIVE_NOT_AVAILABLE');
  }
});
