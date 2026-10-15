import type { components } from "../schema";
import type { Case } from "../client";
export type MissionPreset =
  | "comprehensive"
  | "blockage"
  | "clearance"
  | "recovery";
export type MissionPlan = {
  submission_id?: string | null;
  navigation_strategy?: Record<string, unknown> | null;
  mission_id: string;
  title: string;
  preset: MissionPreset;
  config_id: string;
  family: string;
  seed: number;
  brief: string;
  case_ids: string[];
  max_cases: number;
  max_actions: number;
  available_cases: number;
  compare_strategies: boolean;
  notes: string[];
  steps: string[];
  limits: string[];
  scene_hash: string;
  task_hash: string;
  constraints_hash: string;
  scene: components["schemas"]["SceneView"];
  task: components["schemas"]["TaskView"];
};
export type Submission = {
  submission_id: string;
  filename: string;
  content: string;
  content_sha256: string;
  status: "READY" | "STATIC_ONLY";
  strategy: Record<string, unknown> | null;
  findings: string[];
  analysis_source: string;
};
export type GeneratedScene = Pick<
  MissionPlan,
  "config_id" | "scene" | "task" | "seed" | "scene_hash"
> & {
  generator_version: string;
  baseline_audit: { status: string };
  baseline_path: number[][];
};
export type EvidenceAnswer = {
  source: string;
  answer: string;
  citations: { case_id: string; path_id: string; evidence_id: string | null }[];
};
export type EvidenceChatRecord = {
  request_id: string;
  question: string;
  status: "PENDING" | "COMPLETED" | "ERROR";
  response?: EvidenceAnswer;
  error_code?: string;
};
export type PublicDecision = {
  phase: string;
  summary: string;
  timestamp: string;
  source: string;
  case_id: string;
  evidence_ids: string[];
  case_order: string[];
};
export function caseOutcome(c: Case) {
  const original = c.paths.find((p) => p.role === "original");
  const latest = c.paths.at(-1);
  if (c.stopped)
    return {
      label: "安全停止",
      tone: "amber",
      detail: "未到达目标，保留停止依据",
    };
  if (latest?.audit_status === "PASS")
    return latest.role === "recovery"
      ? {
          label: "恢复通过",
          tone: "cyan",
          detail: "新路线通过，原始失败仍保留",
        }
      : { label: "原始通过", tone: "green", detail: "原始路线通过独立验收" };
  if (latest?.audit_status === "FAIL" || original?.audit_status === "FAIL")
    return {
      label: "待处理失败",
      tone: "red",
      detail: "已有失败证据，尚无通过的恢复路线",
    };
  return {
    label: "证据不足",
    tone: "muted",
    detail: latest ? "等待独立验收" : "尚未执行",
  };
}
