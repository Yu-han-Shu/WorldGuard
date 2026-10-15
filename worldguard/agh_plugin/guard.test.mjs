import assert from 'node:assert/strict';
import test from 'node:test';
import { boundedGuard, createGuard, toolNames } from './index.mjs';
import { boundedProvider } from './provider_guard.mjs';
import { setTimeout as delay } from 'node:timers/promises';

const config = { allowed: true, model: 'fixture-model', maxRequests: 2, maxTokens: 2000, wallMs: 5000 };
const request = { model: 'fixture-model', slot: 'primary', attempt: 1, request: {} };

test('MOCK hooks count retries and preserve tighter output limits', () => {
  const guard = createGuard(config);
  assert.deepEqual(guard.beforeRequest(request), { patch: { maxTokens: 2000 } });
  assert.deepEqual(guard.beforeRequest({ ...request, attempt: 2, request: { maxTokens: 500 } }),
    { patch: { maxTokens: 500 } });
  assert.throws(() => guard.beforeRequest(request), /MODEL_REQUEST_BUDGET/);
  assert.equal(guard.snapshot().reservedPrimaryAttempts, 2);
});

test('MOCK hooks deny raw names, invented tools and other servers', () => {
  const guard = createGuard(config);
  for (const name of toolNames) assert.deepEqual(guard.toolCall({ name }), { allow: true });
  for (const name of ['bash', 'read', 'wg_health', toolNames[0] + '_fake', 'mcp_other_wg_health']) {
    assert.equal(guard.toolCall({ name }).allow, false);
  }
});

test('MOCK hooks reject disabled calls, route slots and expired sessions', () => {
  const disabled = createGuard({ ...config, allowed: false });
  assert.throws(() => disabled.beforeRequest(request), /MODEL_CALLS_DISABLED/);
  assert.equal(disabled.toolCall({ name: toolNames[0] }).allow, false);
  let now = 0;
  const guard = createGuard(config, () => now);
  assert.throws(() => guard.beforeRequest({ ...request, slot: 'fast' }), /UNEXPECTED_MODEL_SLOT/);
  assert.throws(() => guard.beforeRequest({ ...request, model: 'other' }), /UNEXPECTED_MODEL_SLOT/);
  now = 5000;
  assert.equal(guard.beforeStep().block, true);
  assert.throws(() => guard.beforeRequest(request), /WALL_TIME_EXHAUSTED/);
});

test('MOCK plugin registers official hooks and requires explicit configuration', () => {
  const old = process.env.WORLDGUARD_AGH_GUARD;
  try {
    delete process.env.WORLDGUARD_AGH_GUARD;
    assert.throws(() => boundedGuard.apply({}), /INVALID_GUARD_CONFIG/);
    process.env.WORLDGUARD_AGH_GUARD = JSON.stringify({ ...config, allowed: false });
    const hooks = {};
    boundedGuard.apply({ extension: () => ({ registerHook: (name, callback) => { hooks[name] = callback; } }) });
    assert.equal(Object.keys(hooks).length, 3);
    assert.throws(() => hooks.before_request(request), /MODEL_CALLS_DISABLED/);
  } finally {
    if (old === undefined) delete process.env.WORLDGUARD_AGH_GUARD;
    else process.env.WORLDGUARD_AGH_GUARD = old;
  }
});

test('MOCK provider counts auxiliary requests, denies excess and disables wire retries', async () => {
  const calls = [];
  const inner = { models: () => [], async *infer(req, options) {
    calls.push({ req, options });
    yield { type: 'usage', tokens: { input: 5, output: 3 } };
    yield { type: 'done', reason: 'stop' };
  } };
  const cfg = { allowed: true, route: 'fixture', model: 'test', maxRequests: 2,
    maxTokens: 2000, wallMs: 5000, toolNames };
  const guard = boundedProvider(inner, cfg);
  const req = { route: 'fixture', model: 'test', sampling: { maxTokens: 1000 }, tools: [] };
  const opt = { signal: new AbortController().signal, toolNames: [] };
  const collect = async (request) => Array.fromAsync(guard.infer(request, opt));
  await collect(req);
  await collect({ ...req, sessionKey: 'title:fixture', sampling: { maxTokens: 80 } });
  assert.equal((await collect(req))[0].code, 'MODEL_REQUEST_BUDGET');
  assert.equal(calls.length, 2);
  assert(calls.every(call => call.options.retry === false));
  assert.equal(guard.usage().model_requests, 2);
  assert.equal(guard.usage().model_tokens, 16);
  assert.equal(guard.usage().model_usage_complete, true);
});

test('MOCK provider rejects unapproved model, tools, output and disabled inference before dispatch', async () => {
  const inner = { models: () => [], async *infer() { assert.fail('must not dispatch'); } };
  const cfg = { allowed: true, route: 'fixture', model: 'test', maxRequests: 1,
    maxTokens: 2000, wallMs: 5000, toolNames };
  const req = { route: 'fixture', model: 'test', sampling: { maxTokens: 1000 }, tools: [] };
  const opt = { signal: new AbortController().signal, toolNames: [] };
  for (const [change, code] of [
    [{ route: 'other' }, 'UNEXPECTED_MODEL'],
    [{ tools: [{ name: 'shell' }] }, 'UNEXPECTED_TOOL'],
    [{ sampling: { maxTokens: 2001 } }, 'OUTPUT_BUDGET_UNVERIFIED'],
    [{ sampling: {} }, 'OUTPUT_BUDGET_UNVERIFIED'],
  ]) {
    const guard = boundedProvider(inner, cfg);
    const result = await Array.fromAsync(guard.infer({ ...req, ...change }, opt));
    assert.equal(result[0].code, code);
    assert.equal(guard.usage().model_requests, 0);
  }
  const disabled = boundedProvider(inner, { ...cfg, allowed: false });
  assert.equal((await Array.fromAsync(disabled.infer(req, opt)))[0].code, 'MODEL_CALLS_DISABLED');
});

test('MOCK missing auxiliary usage remains unknown rather than counted as zero tokens', async () => {
  const inner = { models: () => [], async *infer() { yield { type: 'done', reason: 'stop' }; } };
  const guard = boundedProvider(inner, { allowed: true, route: 'fixture', model: 'test', maxRequests: 1,
    maxTokens: 2000, wallMs: 5000, toolNames });
  await Array.fromAsync(guard.infer({ route: 'fixture', model: 'test', tools: [], sampling: { maxTokens: 80 } },
    { signal: new AbortController().signal, toolNames: [] }));
  assert.equal(guard.usage().model_tokens, null);
  assert.equal(guard.usage().unreported_model_requests, 1);
});

const providerConfig = { allowed: true, route: 'fixture', model: 'test', maxRequests: 2,
  maxTokens: 2000, wallMs: 1000, requestTimeoutMs: 25, toolNames };
const providerRequest = { route: 'fixture', model: 'test', sampling: { maxTokens: 80 }, tools: [] };
const providerOptions = () => ({ signal: new AbortController().signal, toolNames: [] });

test('MOCK slow request times out distinctly and retry consumes another reserved attempt', async () => {
  let attempts = 0;
  const diagnostics = [];
  const inner = { models: () => [], async *infer(req, options) {
    attempts++;
    if (attempts === 1) await delay(500, undefined, { signal: options.signal });
    yield { type: 'usage', tokens: { input: 5, output: 1 } };
    yield { type: 'done', reason: 'stop' };
  } };
  const guard = boundedProvider(inner, providerConfig, row => diagnostics.push(row));
  const first = await Array.fromAsync(guard.infer(providerRequest, providerOptions()));
  assert.equal(first[0].code, 'TIMEOUT');
  assert.equal(first[0].message, 'MODEL_REQUEST_TIMEOUT');
  assert.equal(first[0].retryable, true);
  assert.equal(diagnostics.find(row => row.failure)?.failure.code, 'MODEL_REQUEST_TIMEOUT');
  assert.equal((await Array.fromAsync(guard.infer(providerRequest, providerOptions()))).at(-1).type, 'done');
  assert.equal(guard.usage().model_requests, 2);
  assert.equal(guard.usage().model_tokens, null);
  assert.equal(guard.usage().unreported_model_requests, 1);
  assert.equal((await Array.fromAsync(guard.infer(providerRequest, providerOptions())))[0].code, 'MODEL_REQUEST_BUDGET');
  assert.equal(attempts, 2);
});

test('MOCK configured longer deadline allows a slow successful response', async () => {
  const inner = { models: () => [], async *infer(req, options) {
    await delay(55, undefined, { signal: options.signal });
    yield { type: 'done', reason: 'stop' };
  } };
  const guard = boundedProvider(inner, { ...providerConfig, requestTimeoutMs: 250 });
  assert.equal((await Array.fromAsync(guard.infer(providerRequest, providerOptions())))[0].type, 'done');
});

test('MOCK upstream abort event caused by our timer is classified as timeout', async () => {
  const inner = { models: () => [], async *infer(req, options) {
    try { await delay(500, undefined, { signal: options.signal }); } catch {
      yield { type: 'error', reason: 'aborted', code: 'ABORTED', message: 'aborted', retryable: false };
    }
  } };
  const guard = boundedProvider(inner, providerConfig);
  assert.equal((await Array.fromAsync(guard.infer(providerRequest, providerOptions())))[0].code, 'TIMEOUT');
});

test('MOCK cancellation is never retried or relabeled as timeout', async () => {
  const control = new AbortController();
  const inner = { models: () => [], async *infer(req, options) {
    control.abort();
    await delay(500, undefined, { signal: options.signal });
    yield { type: 'done' };
  } };
  const guard = boundedProvider(inner, providerConfig);
  const event = (await Array.fromAsync(guard.infer(providerRequest, { signal: control.signal })))[0];
  assert.equal(event.code, 'ABORTED');
  assert.equal(event.retryable, false);
  await Array.fromAsync(guard.infer(providerRequest, { signal: control.signal }));
  assert.equal(guard.usage().model_requests, 1);
});

test('MOCK shared wall deadline stops a request before its longer per-request limit', async () => {
  const inner = { models: () => [], async *infer(req, options) {
    await delay(500, undefined, { signal: options.signal });
    yield { type: 'done' };
  } };
  const guard = boundedProvider(inner, { ...providerConfig, requestTimeoutMs: 200, deadlineMs: Date.now() + 25 });
  const event = (await Array.fromAsync(guard.infer(providerRequest, providerOptions())))[0];
  assert.equal(event.code, 'WALL_TIME_EXHAUSTED');
  assert.equal(event.retryable, false);
});

test('MOCK 429 respects Retry-After and keeps quota and request limits separate', async () => {
  const starts = [], diagnostics = [];
  const inner = { models: () => [], async *infer() {
    starts.push(Date.now());
    if (starts.length === 1) yield { type: 'error', reason: 'error', code: 'RATE_LIMIT',
      message: 'PRIVATE_PROVIDER_TEXT', retryable: true, retryAfterMs: 60 };
    else yield { type: 'error', reason: 'error', code: 'QUOTA', message: 'PRIVATE', retryable: false };
  } };
  const guard = boundedProvider(inner, providerConfig, row => diagnostics.push(row));
  await Array.fromAsync(guard.infer(providerRequest, providerOptions()));
  await Array.fromAsync(guard.infer(providerRequest, providerOptions()));
  assert(starts[1] - starts[0] >= 50);
  assert.deepEqual(diagnostics.filter(row => row.failure).map(row => row.failure.code),
    ['MODEL_RATE_LIMIT', 'MODEL_QUOTA_EXHAUSTED']);
  assert(!JSON.stringify(diagnostics).includes('PRIVATE'));
  assert.equal(guard.usage().model_requests, 2);
});

test('MOCK rate-limit wait cannot bypass wall budget or cancellation', async () => {
  let calls = 0;
  const inner = { models: () => [], async *infer() {
    calls++;
    yield { type: 'error', reason: 'error', code: 'RATE_LIMIT', retryAfterMs: 2000, retryable: true };
  } };
  const guard = boundedProvider(inner, providerConfig);
  await Array.fromAsync(guard.infer(providerRequest, providerOptions()));
  assert.equal((await Array.fromAsync(guard.infer(providerRequest, providerOptions())))[0].code, 'WALL_TIME_EXHAUSTED');
  assert.equal(calls, 1);
});

test('MOCK hook refusal preserves exact budget reason even when Host wraps errors', () => {
  const failures = [];
  const guard = createGuard({ ...config, maxRequests: 1 }, Date.now, code => failures.push(code));
  guard.beforeRequest(request);
  assert.throws(() => guard.beforeRequest(request), /MODEL_REQUEST_BUDGET/);
  assert.deepEqual(failures, ['MODEL_REQUEST_BUDGET']);
});
