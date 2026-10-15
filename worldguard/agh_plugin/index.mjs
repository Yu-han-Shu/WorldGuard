// Official extension hooks. This is NOT a provider-wide spending limit:
// the pinned host's background title requests bypass before_request.
import { createHash } from 'node:crypto';

const prefix = `mcp_worldguard_${createHash('sha256').update('worldguard').digest('hex').slice(0, 8)}_`;
export const toolNames = [
  'wg_health', 'wg_create_campaign', 'wg_list_candidates', 'wg_run_case',
  'wg_audit_path', 'wg_recover_case', 'wg_rerun_case', 'wg_read_evidence',
  'wg_finish_campaign', 'wg_stop_campaign', 'wg_optimize_case', 'wg_publish_decision',
].map(name => (prefix + name).slice(0, 64));

export function createGuard(config, now = Date.now, onBlocked = () => {}) {
  config = Object.freeze({ ...config });
  const integer = value => Number.isSafeInteger(value) && value > 0;
  if (!config || typeof config.allowed !== 'boolean' || !integer(config.maxRequests)
      || !integer(config.maxTokens) || !integer(config.wallMs)
      || typeof config.model !== 'string' || !config.model) throw Error('INVALID_GUARD_CONFIG');
  const deadline = config.deadlineMs ?? now() + config.wallMs;
  const deny = code => { onBlocked(code); throw Error(code); };
  let requests = 0;
  const check = () => {
    if (!config.allowed) deny('MODEL_CALLS_DISABLED');
    if (now() >= deadline) deny('WALL_TIME_EXHAUSTED');
  };
  return {
    beforeRequest(input) {
      check();
      if (input.model !== config.model || input.slot !== 'primary') throw Error('UNEXPECTED_MODEL_SLOT');
      if (requests >= config.maxRequests) deny('MODEL_REQUEST_BUDGET');
      requests += 1; // Retry attempts count as well, even if dispatch subsequently fails.
      const existing = input.request?.maxTokens;
      return { patch: { maxTokens: Number.isSafeInteger(existing) && existing > 0
        ? Math.min(existing, config.maxTokens) : config.maxTokens } };
    },
    toolCall(input) {
      try { check(); } catch (error) { return { allow: false, reason: error.message }; }
      return toolNames.includes(input.name)
        ? { allow: true } : { allow: false, reason: 'WORLDGUARD_TOOL_ONLY' };
    },
    beforeStep() {
      try { check(); return {}; } catch (error) { return { block: true, reason: error.message }; }
    },
    snapshot() { return { reservedPrimaryAttempts: requests }; },
  };
}

export const boundedGuard = {
  inject: ['extension'],
  apply(ctx) {
    // No implicit approval or guessed route. Environment contains limits, never a key.
    const guard = createGuard(JSON.parse(process.env.WORLDGUARD_AGH_GUARD ?? 'null'), Date.now,
      code => process.stdout.write(JSON.stringify({ type: 'guard_failure', code }) + '\n'));
    const api = ctx.extension();
    api.registerHook('before_request', input => guard.beforeRequest(input));
    api.registerHook('tool_call', input => guard.toolCall(input));
    api.registerHook('before_step', () => guard.beforeStep());
  },
};

export const presets = {
  'worldguard-bounded': {
    name: 'worldguard-bounded',
    extends: 'base',
    model: { max_tokens: 2000, timeout_ms: 90000, retry: { max_attempts: 2 } },
    budget: { max_steps: 30 },
    tools: { core: [], timeout_ms: 45000, output_max_bytes: 32768 },
    compaction: { enabled: false, agent_callable: false },
    subagent: { max_depth: 0, max_fan_out: 0 },
    repair: { max_rounds: 0 },
    completion_gate: { enabled: false },
    harness: { auto_refine: { enabled: false } },
    skills_roots: [],
  },
};

// Host-owned loopback endpoint; no URL or credentials are accepted from model arguments.
export const mcpTools = {
  inject: ['extension'],
  async apply(ctx) {
    const { resolve } = await import('node:path');
    const { pathToFileURL } = await import('node:url');
    const root = process.env.WORLDGUARD_AGH_ROOT;
    const url = new URL(process.env.WORLDGUARD_MCP_URL);
    if (!root || url.protocol !== 'http:' || url.hostname !== '127.0.0.1') {
      throw Error('INVALID_LOCAL_MCP_ENDPOINT');
    }
    const { connectMcp } = await import(pathToFileURL(resolve(root, 'packages/base/src/mcp/connect.ts')));
    const { registerRemoteToolsStrict } = await import(pathToFileURL(resolve(root, 'packages/base/src/mcp/register.ts')));
    const config = {
      id: 'worldguard', transport: 'http', url: url.href, defer: false,
      headers: { Authorization: `Bearer ${process.env.WORLDGUARD_MCP_TOKEN}` },
      allowedTools: toolNames.map(name => name.slice(prefix.length)),
    };
    const connection = await connectMcp(config);
    const api = ctx.extension();
    // Ordinary plugin rows expose tools but intentionally have no resource registration capability.
    // This product has no MCP catalogue UI; retain the official validation/output guard for tools.
    const dispose = await registerRemoteToolsStrict({
      registerResource: () => () => {},
      registerTool: definition => api.registerTool({ ...definition, meta: { ...definition.meta,
        isDestructive: false, isOpenWorld: false, requiresApproval: 'never',
      } }),
      ctx: api.ctx,
    }, connection, config);
    ctx.on('dispose', async () => { dispose(); await connection.close(); });
  },
};
