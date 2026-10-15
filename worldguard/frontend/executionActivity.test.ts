import test from 'node:test';
import assert from 'node:assert/strict';
import { executionActivity, elapsedLabel } from './src/executionStatus.ts';

const now = Date.parse('2026-10-15T00:02:00Z');
const input = { events: [], decisions: [], createdAt: '2026-10-15T00:01:00Z', now, connected: true, jobActive: true };

test('waiting does not invent executed actions or progress', () => {
  const before = executionActivity(input);
  const later = executionActivity({ ...input, now: now + 60_000 });
  assert.equal(before.title, '等待首条执行记录');
  assert.equal(later.title, before.title);
  assert.equal(before.idleSeconds, 60);
  assert.equal(later.idleSeconds, 120);
  assert.equal(input.events.length, 0);
});

test('new tool or public decision timestamps reset observed inactivity', () => {
  const events = [{ timestamp: '2026-10-15T00:01:10Z' }, { timestamp: 'invalid' }];
  const stalled = executionActivity({ ...input, events });
  assert.equal(stalled.idleSeconds, 50);
  assert.match(stalled.description, /暂时没有新记录/);
  const updated = executionActivity({ ...input, events, decisions: [{ timestamp: '2026-10-15T00:01:58Z' }] });
  assert.equal(updated.idleSeconds, 2);
  assert.equal(updated.title, '等待下一步结果');
  assert.doesNotMatch(updated.description, /暂时没有新记录/);
});

test('connection loss and queueing are not presented as active execution', () => {
  assert.equal(executionActivity({ ...input, connected: false }).title, '连接暂时中断');
  assert.equal(executionActivity({ ...input, jobActive: false }).title, '等待任务调度');
  assert.equal(executionActivity({ ...input, jobActive: false, manual: true }).title, '等待手动操作');
  assert.equal(executionActivity({ ...input, jobActive: false, interrupted: true }).title, '执行已中断');
});

test('missing or future timestamps never produce NaN or negative timers', () => {
  assert.equal(executionActivity({ ...input, createdAt: null }).idleSeconds, null);
  assert.equal(executionActivity({ ...input, events: [{ timestamp: '2026-10-15T00:03:00Z' }] }).idleSeconds, 0);
  assert.equal(elapsedLabel(NaN), '0 秒');
  assert.equal(elapsedLabel(-2), '0 秒');
  assert.equal(elapsedLabel(95.9), '1 分 35 秒');
});
