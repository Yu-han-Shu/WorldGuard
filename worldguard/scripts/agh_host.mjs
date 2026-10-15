// Production AGH Host + official wire adapter + official MCP registration, in an isolated home.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, mkdirSync, writeFileSync, appendFileSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { presets, toolNames } from '../agh_plugin/index.mjs';
import { boundedProvider } from '../agh_plugin/provider_guard.mjs';

const options = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const deadlineMs = options.deadline_epoch_ms ?? Date.now() + options.wall_seconds * 1000;
const requestTimeoutMs = (options.request_timeout_seconds ?? Math.min(90, options.wall_seconds)) * 1000;
const remainingMs = () => Math.max(1, deadlineMs - Date.now());
const runtimePresets = { 'worldguard-bounded': { ...presets['worldguard-bounded'],
  model: { ...presets['worldguard-bounded'].model, timeout_ms: requestTimeoutMs } } };
const root = resolve(options.agh_root);
const imp = path => import(pathToFileURL(join(root, path)).href);
const hostAPI = await imp('packages/host/src/index.ts');
const { buildProvider } = await imp('packages/host/src/assemble/provider.ts');
const { scanAll } = await imp('packages/core/src/index.ts');
const { hashDirectory } = await imp('packages/package-manager/src/index.ts');
const { createPluginRow, buildRuntimeTarget } = await imp('packages/plugin-runtime/src/host/index.ts');
const emit = value => {
  const line = JSON.stringify(value) + '\n';
  appendFileSync(join(options.home, 'progress.jsonl'), line);
  process.stdout.write(line);
};
const log = { debug() {}, info() {}, warn() {}, error() {} };
const home = resolve(options.home), cwd = resolve(options.workspace);
mkdirSync(home, { recursive: true });
const configuration = hostAPI.createConfigurationService({ home: options.credential_home, profile: 'local-dev' });
const input = await configuration.profileInput();
let route = input.provider?.routes?.find(r => new URL(r.baseUrl).origin === 'https://api.agnes-ai.cn'
  && r.credentialRef?.startsWith('secret://agnes-ai/'));
assert(route, 'AGNES_ROUTE_NOT_CONFIGURED');
let model = route.models.find(m => m.id === 'agnes-3.0-flash');
assert(model, 'AGNES_MODEL_NOT_CONFIGURED');
let kimiKey;
if (options.provider === 'Kimi') {
  const credential = JSON.parse(readFileSync(options.kimi_credentials, 'utf8').replace(/^\uFEFF/, ''));
  assert(credential.base_url === 'https://api.kimi.com/coding/v1', 'INVALID_KIMI_ENDPOINT');
  assert(credential.model === 'kimi-for-coding' && credential.api_key, 'INVALID_KIMI_CONFIG');
  kimiKey = credential.api_key;
  model = { ...model, id: credential.model, name: 'Kimi for Coding', route: 'worldguard-kimi',
    api: 'openai-completions', baseUrl: credential.base_url, reasoning: false,
    contextWindow: 128000, maxTokens: 2000 };
  route = { route: 'worldguard-kimi', api: 'openai-completions', baseUrl: credential.base_url,
    credentialRef: 'secret://worldguard/kimi', models: [model],
    headers: { 'User-Agent': 'WorldGuard/1.0 (Agnes-Harness)' } };
}
const selected = { ...route, models: [model] };
const profile = await hostAPI.resolveProfile({ builtin: 'local-dev', user: {
  ...input, name: 'local-dev', provider: { ...input.provider, routes: [selected], catalog: { include: [] } },
  dataDir: join(home, 'data'), cacheDir: join(home, 'cache'),
  transports: [], computerUse: { enabled: false },
  packages: [{ id: '@agnes/code', source: 'builtin', enabled: false }],
  presets: { default: 'worldguard-bounded', allowed: ['worldguard-bounded'] },
} }, { platform: hostAPI.createPlatform().snapshot(), agnesVersion: '0.1.0', now: new Date().toISOString(), homeDir: home });
const built = await buildProvider(profile, { primary: { route: route.route, model: model.id } }, {
  secrets: ref => ref === 'secret://worldguard/kimi' ? kimiKey
    : hostAPI.createSecretsFile({ dir: input.adapters.secrets.path }).resolve(ref),
  clock: Date.now, log,
});
const guarded = boundedProvider(built.provider, {
  allowed: options.allowed === true, route: route.route, model: model.id,
  maxRequests: options.max_requests, maxTokens: options.max_tokens,
  wallMs: options.wall_seconds * 1000, deadlineMs, requestTimeoutMs, toolNames,
}, value => emit({ type: 'usage', ...value }));
const loader = hostAPI.createJitiPackageLoader({ import: file => import(pathToFileURL(file).href) });
const pluginDir = resolve(options.plugin_directory);
const pkg = JSON.parse(readFileSync(join(pluginDir, 'package.json'), 'utf8'));
const hash = hashDirectory(pluginDir, { exclude: [] });
const digest = hash.replace(/^sha256-/, '');
const snapshotId = `sha256-${digest}`;
const snapshot = { snapshotId, profile: 'local-dev', packageId: pkg.name, version: pkg.version,
  integrity: snapshotId, treeIntegrity: hash, capabilityHash: hash, directory: pluginDir, contributions: [] };
process.env.WORLDGUARD_AGH_ROOT = root;
process.env.WORLDGUARD_MCP_URL = options.mcp_url;
process.env.WORLDGUARD_AGH_GUARD = JSON.stringify({ allowed: options.allowed === true, model: model.id,
  maxRequests: options.max_requests, maxTokens: options.max_tokens, wallMs: options.wall_seconds * 1000, deadlineMs });
let host, session;
try {
  host = await hostAPI.createHost(profile, {
    dataDir: profile.dataDir, profileDir: join(home, 'profiles/local-dev'), workspaceRoot: cwd,
    homeDir: home, hostRoot: join(root, 'packages/cli'), agnesVersion: '0.1.0', log,
    packageDirs: new Map(profile.packages.filter(p => p.enabled).map(p => [p.id, join(root, 'packages', p.id.slice(7))])),
    loader: { async importPackage(id, dir) {
      const module = await loader.importPackage(id, dir);
      return id === '@agnes/base' ? { ...module, presets: { ...module.presets, ...runtimePresets } } : module;
    } },
    providerFactory: () => guarded,
    runtimePluginCatalogue: [{ snapshot, generation: 1, trusted: true }],
    extensionLoader: { import: file => import(pathToFileURL(file).href) },
  });
  emit({ type: 'stage', stage: 'host_assembled' });
  // Remove the ordinary coding/search/subagent extensions through Host's own row lifecycle.
  await host.extensionRows.apply(host.extensionRows.current().map(row => host.extensionRows.prepare({
    extensionId: row.id.slice(4), disabled: row.id !== 'ext:agnes/hooks-runner',
  })));
  const rows = pkg.agnes.plugins.map(declaration => createPluginRow({
    id: declaration.id, plugin: `${pkg.name}@${snapshotId}/${declaration.export}`,
    snapshotDigest: snapshotId, exportName: declaration.export, entryRevision: snapshotId,
    extrasRevision: 'none', mountRevision: 'host-ordinary-row:v1', inject: ['extension'],
  }));
  const report = await host.applyRuntimeTarget(buildRuntimeTarget({ rows,
    resources: { mcp: [], skills: {} }, resourceRevision: digest, compositeRevision: digest }));
  emit({ type: 'stage', stage: 'plugins_applied', rows: report.rows.map(r => ({ id: r.id, state: r.state })) });
  assert(rows.every(row => report.rows.some(r => r.id === row.id && r.state === 'active')), 'PLUGIN_HOST_NOT_READY');
  emit({ type: 'ready', route: route.route, model: model.id, plugin_host: 'PASS',
    tool_names: host.kernel.tools.list().map(t => t.name).filter(n => toolNames.includes(n)) });
  if (options.probe_only) {
    emit({ type: 'result', runtime_mode: 'OFFLINE_PROBE', ...guarded.usage(), plugin_host: 'PASS' });
  } else {
    session = await host.createSession({ cwd, preset: 'worldguard-bounded', key: `agnes:local:local-dev:wg:${options.run_id}` });
    emit({ type: 'stage', stage: 'session_open' });
    await session.enqueue('next-turn', { actor: session.d.actor, kind: 'prompt',
      content: [{ type: 'text', text: options.prompt }] });
    const wallSignal = AbortSignal.timeout(remainingMs());
    const result = await session.run({ until: 'turn-end', signal: wallSignal });
    emit({ type: 'stage', stage: 'turn_ended', reason: result.reason });
    const events = await scanAll(q => session.scan(q), { fromSeq: 1, toSeq: result.lastSeq });
    const terminal = [...events].reverse().find(row => row.type === 'turn/end');
    const knownCodes = new Set(['TIMEOUT', 'RATE_LIMIT', 'QUOTA', 'AUTH', 'TRANSPORT', 'ABORTED',
      'MODEL_REQUEST_BUDGET', 'WALL_TIME_EXHAUSTED']);
    const errorCode = wallSignal.aborted ? 'WALL_TIME_EXHAUSTED'
      : knownCodes.has(terminal?.data?.error?.code) ? terminal.data.error.code : null;
    await session.close();
    const ledger = events.map(row => {
      const data = row.type === 'request/sent' ? { model: row.data.model }
        : row.type === 'tool/call' ? { toolUseId: row.data.toolUseId, name: row.data.name, args: row.data.args }
        : row.type === 'tool/result' ? { toolUseId: row.data.toolUseId, isError: row.data.isError, content: row.data.content }
        : row.type === 'turn/end' ? { reason: row.data.reason, error_code: errorCode }
        : row.type === 'effect/settled' ? { outcome: row.data.outcome, durationMs: row.data.durationMs } : {};
      return JSON.stringify({ seq: row.seq, ts: row.ts, type: row.type, data });
    }).join('\n') + '\n';
    writeFileSync(options.ledger_path, ledger);
    emit({ type: 'result', runtime_mode: 'LIVE_AGNES', reason: result.reason, error_code: errorCode, session_id: session.key,
      route: route.route, model: model.id, ledger_sha256: createHash('sha256').update(ledger).digest('hex'),
      ...guarded.usage(), plugin_host: 'PASS' });
  }
} catch (error) {
  emit({ type: 'failure', code: typeof error.code === 'string' ? error.code : 'AGH_HOST_FAILURE',
    message: String(error.message).replace(/[A-Z]:[\\/][^\s]+/gi, 'LOCAL_PATH').slice(0, 300), ...guarded.usage() });
  process.exitCode = 1;
} finally {
  await session?.close().catch(() => {});
  await host?.close().catch(() => {});
  emit({ type: 'stage', stage: 'host_closed' });
  // The one-shot owner is finished. SDK transport pools can retain idle handles after Host teardown.
  await new Promise(done => process.stdout.write('', done));
  process.exit(process.exitCode ?? 0);
}
