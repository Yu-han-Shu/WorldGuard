import { createWorldGuardClient } from './client.ts';

// Connect this function to the UI's Start button. Save run_id to resume viewing after refresh.
export async function startDemo() {
  const api = createWorldGuardClient();
  const run = await api.createRun({config_id: 'dual_route_stale',
    request_id: crypto.randomUUID(), execution_mode: 'automatic', tester: 'AdaptiveRule'});
  return run.state.run_id;
}

// Invoke every 500–1000 ms while job_active, drain has_more before the next scheduled poll.
export async function readProgress(runId: string, cursor = 0, signal?: AbortSignal) {
  const api = createWorldGuardClient();
  const [run, events] = await Promise.all([api.getRun(runId, signal), api.events(runId, cursor, signal)]);
  return {run, events, nextCursor: events.next_cursor,
    report: run.report_available ? await api.report(runId) : null};
}
