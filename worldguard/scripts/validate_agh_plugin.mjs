// Read-only validation against the pinned checkout's actual exported validators.
// Run using that checkout's tsx CLI. No host, daemon or provider is started.
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import assert from 'node:assert/strict';
import { boundedGuard, presets, toolNames } from '../agh_plugin/index.mjs';

const root = resolve(process.argv[2]);
const { validatePreset, validateHook } = await import(pathToFileURL(resolve(root, 'packages/protocol/src/index.ts')));
const { mcpLocalToolPrefix } = await import(pathToFileURL(resolve(root, 'packages/base/src/mcp/naming.ts')));
assert.equal(toolNames[0], `${mcpLocalToolPrefix('worldguard')}wg_health`);
for (const preset of Object.values(presets)) {
  const result = validatePreset(preset);
  assert.equal(result.ok, true, JSON.stringify(result));
}
const previous = process.env.WORLDGUARD_AGH_GUARD;
try {
  process.env.WORLDGUARD_AGH_GUARD = JSON.stringify({
    allowed: true, model: 'offline-fixture', maxRequests: 1, maxTokens: 2000, wallMs: 5000,
  });
  const hooks = {};
  boundedGuard.apply({ extension: () => ({ registerHook(name, fn) { hooks[name] = fn; } }) });
  for (const [name, input] of [
    ['before_request', { model: 'offline-fixture', slot: 'primary', request: {}, attempt: 1 }],
    ['tool_call', { name: toolNames[0] }],
    ['before_step', {}],
  ]) {
    const result = validateHook(name, 'return', hooks[name](input));
    assert.equal(result.ok, true, JSON.stringify(result));
  }
} finally {
  if (previous === undefined) delete process.env.WORLDGUARD_AGH_GUARD;
  else process.env.WORLDGUARD_AGH_GUARD = previous;
}
console.log('OFFICIAL_SCHEMA_PASS; plugin host loading NOT_RUN; provider calls 0');
