import { useEffect, useState } from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  Check,
  Fingerprint,
  FlaskConical,
  GitBranch,
  LoaderCircle,
  LockKeyhole,
  Pause,
  Play,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import type { Case, components } from "../client";
import { api } from "./useWorkbench";
import { SceneMap } from "./SceneMap";

type S = components["schemas"];
type Experiment = S["ExperimentView"];
type Passport = S["PassportView"];
type Probe = S["PassportProbeView"];
const meters = (n: number | null | undefined) =>
  typeof n === "number" ? n.toFixed(3) + " m" : "—";
const fieldNames: Record<string, string> = {
  environment_hash: "真实地图",
  task_hash: "起终点与任务",
  constraints_hash: "机器人约束",
  path_hash: "路径指纹",
  verifier_version: "验收器版本",
};
const changes: Record<string, string> = {
  planner_map: "规划器地图",
  strategy_parameters: "策略参数",
  planner_implementation: "导航器实现",
};
const download = (name: string, value: unknown) => {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
function pathRecord(
  caseId: string,
  id: string,
  plan: S["PlanView"],
  audit: S["AuditView"],
): Case["paths"] {
  return [
    {
      case_id: caseId,
      path_id: id,
      role: "original",
      plan,
      audit_status: audit.status,
      audit: { case_id: caseId, path_id: id, audit, evidence_id: null },
    },
  ];
}
function errorText(e: unknown) {
  const code = e instanceof Error ? e.message : "";
  return (
    {
      EXPERIMENT_WAIT_FOR_COMPLETION:
        "请等待本轮评测结束，再对冻结结果进行实验。",
      EXPERIMENT_REQUIRES_AUDITED_PATH: "这个案例还没有已验收的原始路径。",
      EXPERIMENT_PLANNER_UNSUPPORTED: "这条历史记录的导航器暂不支持重放。",
    }[code] || "暂时无法完成请求，请检查本地服务后重试。"
  );
}

export function ExperimentLab({
  value,
  cases,
  running,
  onCase,
}: {
  value: Case;
  cases: Case[];
  running: boolean;
  onCase: (id: string) => void;
}) {
  const [mode, setMode] = useState<"experiment" | "passport">("experiment");
  return (
    <div className="experiment-lab">
      <div className="lab-heading">
        <div>
          <span className="lab-eyebrow">WORLDGUARD · EXPERIMENT LAB</span>
          <h2>从发现问题，到解释改进</h2>
          <p>同一个现场，比较干预；每一条结论，关联证据。</p>
        </div>
        <FlaskConical size={29} />
      </div>
      <div className="lab-controls">
        <div role="tablist" aria-label="实验功能">
          <button
            role="tab"
            aria-selected={mode === "experiment"}
            onClick={() => setMode("experiment")}
          >
            <GitBranch size={15} />
            反事实实验
          </button>
          <button
            role="tab"
            aria-selected={mode === "passport"}
            onClick={() => setMode("passport")}
          >
            <Fingerprint size={15} />
            证据护照
          </button>
        </div>
        <select
          aria-label="实验案例"
          value={value.candidate.case_id}
          onChange={(e) => onCase(e.target.value)}
        >
          {cases.map((c) => (
            <option key={c.candidate.case_id} value={c.candidate.case_id}>
              {c.candidate.case_id === "normal"
                ? "正常基准"
                : c.candidate.case_id
                    .replace("block_route_", "堵路案例 ")
                    .replace("pinch_clearance_", "窄通道 ")
                    .replace("disconnect_goal_", "目标隔断 ")}
            </option>
          ))}
        </select>
      </div>
      {mode === "experiment" ? (
        <Counterfactual
          key={value.run_id + value.candidate.case_id}
          value={value}
          running={running}
        />
      ) : (
        <EvidencePassport
          key={value.run_id + value.candidate.case_id}
          value={value}
        />
      )}
    </div>
  );
}

function Counterfactual({ value, running }: { value: Case; running: boolean }) {
  const [data, setData] = useState<Experiment | null>(null);
  const [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  const [selected, setSelected] = useState("refresh");
  const [progress, setProgress] = useState(0),
    [playing, setPlaying] = useState(false);
  useEffect(() => {
    let active = true;
    api
      .experiment(value.run_id, value.candidate.case_id)
      .then((d) => {
        if (active) setData(d);
      })
      .catch((e) => {
        if (active && e.code !== "EXPERIMENT_NOT_READY") setError(errorText(e));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [value.run_id, value.candidate.case_id]);
  useEffect(() => {
    if (!playing) return;
    const timer = setInterval(
      () => setProgress((p) => Math.min(100, p + 0.5)),
      40,
    );
    return () => clearInterval(timer);
  }, [playing]);
  useEffect(() => {
    if (progress >= 100) setPlaying(false);
  }, [progress]);
  async function run() {
    setBusy(true);
    setError("");
    try {
      setData(
        await api.experiment(value.run_id, value.candidate.case_id, true),
      );
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  const candidate = data?.branches.find((b) => b.id === selected);
  const original = data?.branches[0];
  return (
    <>
      {error && (
        <p role="alert" className="lab-error">
          {error}
        </p>
      )}
      {!data ? (
        <div className="lab-launch">
          <div className={"lab-orbit " + (busy ? "is-running" : "")}>
            <GitBranch size={35} />
            <i />
            <i />
          </div>
          <h3>{busy ? "正在运行对照实验" : "如果换一步处理，结果会怎样？"}</h3>
          <p>
            复制当前案例，固定真实障碍、目标和机器人尺寸，分别验证地图更新与净空策略。
          </p>
          <div className="lab-branch-preview">
            <span>
              A <b>保持原方案</b>
            </span>
            <ArrowRight size={15} />
            <span>
              B <b>只更新地图</b>
            </span>
            <ArrowRight size={15} />
            <span>
              C <b>再调整策略</b>
            </span>
          </div>
          <button
            className="studio-primary"
            disabled={
              busy ||
              loading ||
              running ||
              !value.paths.some((p) => p.role === "original" && p.audit)
            }
            onClick={() => void run()}
          >
            {busy || loading ? (
              <LoaderCircle size={16} className="studio-spin" />
            ) : (
              <FlaskConical size={16} />
            )}{" "}
            {busy ? "正在规划并独立验收…" : "运行反事实实验"}
          </button>
          <small>
            {running
              ? "当前评测完成后可运行"
              : "额外 2 次规划 · 0 次模型请求 · 不改写原始结果"}
          </small>
        </div>
      ) : (
        <>
          <div className="lab-frozen">
            <LockKeyhole size={14} />
            同一真实地图 · 同一起终点 · 同一机器人与验收规则
            <span>条件已冻结</span>
          </div>
          <div className="lab-branches">
            {data.branches.map((b, i) => (
              <button
                key={b.id}
                onClick={() => {
                  if (i) {
                    setSelected(b.id);
                    setProgress(0);
                    setPlaying(false);
                  }
                }}
                aria-pressed={i === 0 || selected === b.id}
                disabled={i === 0}
              >
                <span className="lab-branch-id">{"ABC"[i]}</span>
                <b>{b.label}</b>
                <span className={"lab-verdict " + b.outcome.toLowerCase()}>
                  {b.outcome === "PASS" ? (
                    <Check size={13} />
                  ) : (
                    <TriangleAlert size={13} />
                  )}{" "}
                  {b.outcome === "PASS"
                    ? "验收通过"
                    : b.outcome === "REJECTED"
                      ? "验收拒绝"
                      : "结果未定"}
                </span>
                <small>
                  {i === 0
                    ? "保留原始路径，重新验收"
                    : b.changes.length
                      ? "相对" +
                        (i === 1 ? " A：" : " B：") +
                        b.changes.map((c) => changes[c] || c).join("、")
                      : "与上一步相同条件复验"}
                </small>
              </button>
            ))}
          </div>
          {original && candidate && (
            <>
              <div className="lab-map-pair">
                {[original, candidate].map((b, i) => (
                  <figure key={b.id}>
                    <figcaption>
                      <span>{i === 0 ? "原始现场" : b.label}</span>
                      <b className={b.eligible ? "green" : "red"}>
                        {b.eligible
                          ? "PASS"
                          : b.audit.status === "FAIL"
                            ? "FAIL"
                            : "未定"}
                      </b>
                    </figcaption>
                    <SceneMap
                      scene={data.scene}
                      task={data.task}
                      before={data.before}
                      compact
                      timelineProgress={progress}
                      paths={pathRecord(data.case_id, b.id, b.plan, b.audit)}
                      pathColor={i === 0 ? "#f4b957" : "#7ce7d2"}
                    />
                  </figure>
                ))}
              </div>
              <div className="lab-playback">
                <button
                  aria-label={playing ? "暂停同步回放" : "同步回放"}
                  onClick={() => {
                    if (progress >= 100) setProgress(0);
                    setPlaying(!playing);
                  }}
                >
                  {playing ? <Pause size={15} /> : <Play size={15} />}
                </button>
                <input
                  aria-label="同步路径进度"
                  type="range"
                  min="0"
                  max="100"
                  value={progress}
                  onChange={(e) => {
                    setPlaying(false);
                    setProgress(Number(e.target.value));
                  }}
                />
                <small>路径进度 {Math.round(progress)}% · 非时间仿真</small>
              </div>
              <table className="lab-metrics">
                <thead>
                  <tr>
                    <th>相同条件下的结果</th>
                    <th>原始方案</th>
                    <th>当前对照</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>路径长度</td>
                    <td>{meters(original.metrics.path_length_m)}</td>
                    <td>{meters(candidate.metrics.path_length_m)}</td>
                  </tr>
                  <tr>
                    <td>最小剩余净空</td>
                    <td>
                      {meters(original.metrics.minimum_remaining_clearance_m)}
                    </td>
                    <td>
                      {meters(candidate.metrics.minimum_remaining_clearance_m)}
                    </td>
                  </tr>
                  <tr>
                    <td>规划器返回</td>
                    <td>{original.plan.code}</td>
                    <td>{candidate.plan.code}</td>
                  </tr>
                </tbody>
              </table>
            </>
          )}
          <div className="lab-conclusion">
            <FlaskConical size={19} />
            <div>
              <b>这个实验说明了什么</b>
              <p>{data.conclusion}</p>
            </div>
          </div>
          <div className="lab-footer">
            <span>独立实验 · 新增 {data.planner_evaluations} 次规划</span>
            <button
              onClick={() =>
                download("counterfactual-" + data.case_id + ".json", data)
              }
            >
              <ArrowDownToLine size={14} />
              下载实验记录
            </button>
          </div>
          <details className="lab-details">
            <summary>实验条件与适用范围</summary>
            {data.limits.map((l) => (
              <p key={l}>{l}</p>
            ))}
            <p>指纹：{data.experiment_hash}</p>
          </details>
        </>
      )}
    </>
  );
}

function EvidencePassport({ value }: { value: Case }) {
  const eligible = value.paths.filter((p) => p.audit);
  const [pathId, setPathId] = useState(
    eligible.findLast((p) => p.audit_status === "PASS")?.path_id ||
      eligible.at(-1)?.path_id ||
      "",
  );
  const [data, setData] = useState<Passport | null>(null),
    [probe, setProbe] = useState<Probe | null>(null);
  const [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    if (!pathId) return;
    let active = true;
    setLoading(true);
    setData(null);
    setProbe(null);
    setError("");
    api
      .passport(value.run_id, value.candidate.case_id, pathId)
      .then((d) => {
        if (active) setData(d);
      })
      .catch((e) => {
        if (active) setError(errorText(e));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [value.run_id, value.candidate.case_id, pathId]);
  async function simulate(change: "map" | "robot") {
    if (!data) return;
    setBusy(true);
    setError("");
    try {
      setProbe(
        await api.probePassport(
          value.run_id,
          value.candidate.case_id,
          pathId,
          change,
        ),
      );
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      {eligible.length > 0 && (
        <label className="lab-path-select">
          绑定路径
          <select
            aria-label="护照路径"
            value={pathId}
            disabled={busy}
            onChange={(e) => setPathId(e.target.value)}
          >
            {eligible.map((p, i) => (
              <option key={p.path_id} value={p.path_id}>
                {p.role === "original"
                  ? "原始路径"
                  : p.role === "recovery"
                    ? "恢复路径"
                    : "复测路径"}{" "}
                {i + 1} · {p.audit_status === "PASS" ? "通过" : "未通过"}
              </option>
            ))}
          </select>
        </label>
      )}
      {error && (
        <p role="alert" className="lab-error">
          {error}
        </p>
      )}
      {loading ? (
        <div className="lab-empty">
          <LoaderCircle className="studio-spin" />
          正在重新核对证据绑定…
        </div>
      ) : data ? (
        <>
          <div className={"lab-passport " + (data.valid ? "valid" : "invalid")}>
            <div className="lab-passport-top">
              <span>EVIDENCE PASSPORT</span>
              <Fingerprint size={38} />
            </div>
            <h3>
              {data.valid ? "条件匹配，证据有效" : "这条路径没有有效通过凭据"}
            </h3>
            <p>
              {data.valid
                ? "内容绑定与独立几何复核均通过"
                : "失败证据保留，不为未通过路径签发通行结论"}
            </p>
            <div className="lab-passport-id">
              <span>
                {data.role === "original" ? "原始" : "恢复 / 复测"}路径
              </span>
              <code>{data.path_id.slice(-16)}</code>
            </div>
            <div className="lab-fingerprints">
              {Object.entries(data.binding || {}).map(([k, v]) => (
                <div key={k}>
                  <span>
                    <LockKeyhole size={12} />
                    {fieldNames[k] || k}
                  </span>
                  <code title={v}>
                    {k === "verifier_version" ? v : v.slice(0, 18) + "…"}
                  </code>
                </div>
              ))}
            </div>
          </div>
          {data.valid && (
            <section className="lab-probe">
              <div>
                <h3>改变条件，旧证据还能用吗？</h3>
                <p>在副本中做一次干预，观察凭据和路径分别发生什么。</p>
              </div>
              <div className="lab-probe-actions">
                <button disabled={busy} onClick={() => void simulate("map")}>
                  <GitBranch size={15} />
                  在路径上加障碍
                </button>
                <button disabled={busy} onClick={() => void simulate("robot")}>
                  <ShieldCheck size={15} />
                  增大机器人半径
                </button>
                {probe && (
                  <button disabled={busy} onClick={() => setProbe(null)}>
                    还原副本
                  </button>
                )}
              </div>
              {busy && (
                <p className="lab-working">
                  <LoaderCircle size={15} className="studio-spin" />
                  正在校验变化后的条件…
                </p>
              )}
              {probe && !busy && (
                <div className="lab-probe-result">
                  <div className="lab-probe-title">
                    <TriangleAlert size={19} />
                    <div>
                      <b>
                        {probe.binding_status === "STALE_CERTIFICATE"
                          ? "旧凭据已失效，需要重新验收"
                          : "凭据仍匹配"}
                      </b>
                      <small>{probe.description} · 原始记录未改变</small>
                    </div>
                  </div>
                  <SceneMap
                    scene={probe.scene}
                    before={data.scene}
                    task={probe.task}
                    compact
                    paths={pathRecord(
                      value.candidate.case_id,
                      pathId,
                      probe.plan,
                      probe.audit,
                    )}
                  />
                  <p>
                    变化项：
                    {probe.changed_fields
                      .map((k) => fieldNames[k] || k)
                      .join("、")}
                  </p>
                  <p>
                    副本重新验收：
                    <b
                      className={
                        probe.audit.status === "PASS" ? "green" : "red"
                      }
                    >
                      {probe.audit.status === "PASS"
                        ? "仍通过，但旧凭据不能复用"
                        : probe.audit.status === "FAIL"
                          ? "未通过"
                          : "未定"}
                    </b>{" "}
                    · 剩余净空{" "}
                    {meters(probe.audit.minimum_remaining_clearance_m)}
                  </p>
                </div>
              )}
            </section>
          )}
          <div className="lab-footer">
            <span>绑定校验 + 几何复核</span>
            <button
              onClick={() =>
                download("passport-" + data.path_id + ".json", data)
              }
            >
              <ArrowDownToLine size={14} />
              下载证据护照
            </button>
          </div>
          <p className="lab-scope">{data.scope}</p>
        </>
      ) : (
        !loading && (
          <div className="lab-empty">
            <Fingerprint size={34} />
            <h3>等待路径验收</h3>
            <p>路径有验收记录后，可以检查其内容绑定。</p>
          </div>
        )
      )}
    </>
  );
}
