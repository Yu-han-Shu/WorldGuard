/** Framework-independent browser client. No API key belongs in this module. */
import type { components } from './schema.d.ts';
import type { MissionPlan, MissionPreset, GeneratedScene, EvidenceAnswer, EvidenceChatRecord, Submission } from './src/missionTypes';
export type { components, paths, operations } from './schema.d.ts';
type Schema = components['schemas'];
export type Run = Schema['RunView'];
export type Case = Schema['CaseView'];
export type Report = Schema['ReportView'];
export type Optimization = Schema['OptimizationView'];

export class WorldGuardError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;
  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message); this.name = 'WorldGuardError'; this.status = status;
    this.code = code; this.details = details;
  }
}

export function createWorldGuardClient(baseURL = 'http://127.0.0.1:8520') {
  const base = baseURL.replace(/\/$/, '');
  const runPath = (id: string) => `/api/v1/runs/${encodeURIComponent(id)}`;
  const casePath = (rid: string, cid: string) => `${runPath(rid)}/cases/${encodeURIComponent(cid)}`;
  async function request<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
    const response = await fetch(base + path, {
      method: body === undefined ? 'GET' : 'POST', signal,
      headers: body === undefined ? undefined : {'Content-Type': 'application/json'},
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!response.ok) {
      const value = await response.json().catch(() => ({}));
      throw new WorldGuardError(response.status, value.error?.code ?? 'HTTP_ERROR',
        value.error?.message ?? response.statusText, value.error?.details);
    }
    return response.json() as Promise<T>;
  }
  return {
    health: () => request<Schema['HealthView']>('/api/v1/health'),
    capabilities: () => request<Schema['CapabilitiesView']>('/api/v1/capabilities'),
    configs: () => request<Schema['ConfigPage']>('/api/v1/configs'),
    createRun: (body: Schema['CreateRun']) => request<Run>('/api/v1/runs', body),
    prepareMission: (body: {preset:MissionPreset; config_id:string; max_cases:number; brief:string; submission_id?:string}) => request<MissionPlan>('/api/v1/missions/plan', body),
    submitFile: (filename:string, content:string) => request<Submission>('/api/v1/submissions', {filename,content}),
    generateScene: (seed:number, version: 'v1' | 'v2' = 'v1') => request<GeneratedScene>('/api/v1/scenes/generate', {seed, version}),
    askEvidence: (id:string, question:string, case_id?:string) => request<EvidenceAnswer>(runPath(id) + '/questions', {question, case_id, request_id: crypto.randomUUID()}),
    evidenceChat: (id:string) => request<{items:EvidenceChatRecord[]}>(runPath(id) + '/questions'),
    aghSession: (id: string) => request<NonNullable<Run['agh_session']>>(runPath(id) + '/agh'),
    listRuns: (offset = 0, limit = 50) => request<Schema['RunPage']>(`/api/v1/runs?offset=${offset}&limit=${limit}`),
    getRun: (id: string, signal?: AbortSignal) => request<Run>(runPath(id), undefined, signal),
    stopRun: (id: string) => request<Run>(`${runPath(id)}/stop`, {}),
    finishRun: (id: string) => request<Report>(`${runPath(id)}/finish`, {}),
    candidates: (id: string) => request<Schema['CandidatePage']>(`${runPath(id)}/candidates`),
    getCase: (rid: string, cid: string) => request<Case>(casePath(rid, cid)),
    optimizeCase: (rid: string, cid: string) => request<Optimization>(casePath(rid, cid) + '/optimize', {}),
    optimization: (rid: string, cid: string) => request<Optimization>(casePath(rid, cid) + '/optimization'),
    experiment: (rid: string, cid: string, create = false) => request<Schema['ExperimentView']>(casePath(rid, cid) + '/experiment', create ? {} : undefined),
    passport: (rid: string, cid: string, pathId?: string) => request<Schema['PassportView']>(casePath(rid, cid) + '/passport' + (pathId ? '?path_id=' + encodeURIComponent(pathId) : '')),
    probePassport: (rid: string, cid: string, path_id: string, change: 'map' | 'robot') => request<Schema['PassportProbeView']>(casePath(rid, cid) + '/passport/probe', {path_id, change}),
    runCase: (rid: string, cid: string, request_id: string) =>
      request<Schema['PathRecord']>(`${casePath(rid, cid)}/run`, {request_id}),
    rerunCase: (rid: string, cid: string, request_id: string) =>
      request<Schema['PathRecord']>(`${casePath(rid, cid)}/rerun`, {request_id}),
    auditPath: (rid: string, cid: string, path_id: string) =>
      request<Schema['AuditRecord']>(`${casePath(rid, cid)}/audit`, {path_id}),
    recoverCase: (rid: string, cid: string, body: Schema['RecoverAction']) =>
      request<Schema['PathRecord'] | Schema['StopResult']>(`${casePath(rid, cid)}/recover`, body),
    events: (id: string, cursor = 0, signal?: AbortSignal) =>
      request<Schema['EventPage']>(`${runPath(id)}/events?cursor=${cursor}`, undefined, signal),
    evidence: (rid: string, eid: string) => request<Record<string, unknown>>(
      `${runPath(rid)}/evidence/${encodeURIComponent(eid)}`),
    report: (id: string) => request<Report>(`${runPath(id)}/report`),
    mapURL: (rid: string, cid: string) => base + `${casePath(rid, cid)}/map.svg`,
    exportURL: (id: string) => base + `${runPath(id)}/export`,
    markdownURL: (id: string) => base + `${runPath(id)}/report.md`,
  };
}
