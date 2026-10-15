import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  ArrowUp,
  Bot,
  Box,
  Check,
  CheckCheck,
  ChevronRight,
  CircleHelp,
  Clock3,
  FileText,
  Fingerprint,
  FlaskConical,
  Layers,
  LoaderCircle,
  Map as MapIcon,
  MessageSquare,
  Plus,
  RefreshCw,
  Route,
  ShieldCheck,
  Sparkles,
  Square,
  Target,
  TriangleAlert,
  WandSparkles,
} from "lucide-react";
import { api, eventNames, title, useWorkbench } from "./useWorkbench";
import { SceneMap } from "./SceneMap";
import {
  caseOutcome,
  type MissionPlan,
  type MissionPreset,
  type GeneratedScene,
  type EvidenceAnswer,
  type PublicDecision,
} from "./missionTypes";
import "./agent.css";

type Workbench = ReturnType<typeof useWorkbench>;
const presets: {
  id: MissionPreset;
  title: string;
  subtitle: string;
  icon: typeof ShieldCheck;
  tag: string;
}[] = [
  {
    id: "comprehensive",
    title: "场景全面检查",
    subtitle: "基准 → 故障 → 恢复验证",
    icon: ShieldCheck,
    tag: "推荐起点",
  },
  {
    id: "blockage",
    title: "堵路恢复验证",
    subtitle: "观察地图变化后的绕行能力",
    icon: Route,
    tag: "故障专项",
  },
  {
    id: "clearance",
    title: "窄通道边界测试",
    subtitle: "检查机器人尺寸与通道净空",
    icon: Layers,
    tag: "边界条件",
  },
  {
    id: "recovery",
    title: "恢复策略对比",
    subtitle: "比较路程、转弯与安全间距",
    icon: FlaskConical,
    tag: "四种策略",
  },
];
const phaseNames: Record<string, string> = {
  PLAN: "执行计划",
  FINDING: "发现问题",
  RECOVERY: "下一步行动",
  COMPLETE: "结果说明",
};
const friendlyCase = (id: string) =>
  id === "normal"
    ? "正常基准"
    : `${title(id.replace(/_\d+$/, "").toUpperCase())} · ${id.split("_").at(-1)}`;
const short = (v: string) => v.slice(0, 12);
export function AgentWorkspace({
  w,
  onNavigate,
}: {
  w: Workbench;
  onNavigate: (
    page: "maps" | "strategies" | "reports" | "workspace" | "tasks",
  ) => void;
}) {
  const [view, setView] = useState<"create" | "run">(
    new URLSearchParams(location.search).has("run") ? "run" : "create",
  );
  const [preset, setPreset] = useState<MissionPreset>("comprehensive");
  const [config, setConfig] = useState("fulfillment_stale");
  const [brief, setBrief] = useState("");
  const [maximum, setMaximum] = useState(4);
  const [plan, setPlan] = useState<MissionPlan | null>(null);
  const [generated, setGenerated] = useState<GeneratedScene | null>(null);
  const [seed, setSeed] = useState(20261014);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const liveAvailable = !!w.caps?.runtime_modes.some(
    (m) => m.id === "LIVE_AGNES" && m.available,
  );
  const [runtime, setRuntime] = useState<"LIVE_AGNES" | "DETERMINISTIC">(
    "LIVE_AGNES",
  );
  const [messages, setMessages] = useState<
    {
      role: "user" | "assistant";
      text: string;
      citations?: EvidenceAnswer["citations"];
    }[]
  >([]);
  const [question, setQuestion] = useState("");
  const [follow, setFollow] = useState(true);
  const [inspected, setInspected] = useState<{
    id: string;
    value: unknown;
  } | null>(null);
  const requestEpoch = useRef(0);
  const chatEnd = useRef<HTMLDivElement>(null);
  const runId = w.run?.state.run_id;
  useEffect(() => {
    setMessages([]);
    setInspected(null);
    requestEpoch.current += 1;
  }, [runId]);
  useEffect(() => {
    if (w.caps && !liveAvailable) setRuntime("DETERMINISTIC");
  }, [liveAvailable, w.caps]);
  const sceneConfigs = w.configs.filter((c) => c.stale_view && c.seed === 11);
  const mission = w.run?.mission as unknown as MissionPlan | null;
  const decisions = (w.run?.agent_decisions ||
    []) as unknown as PublicDecision[];
  const active = w.run?.state.status === "RUNNING";
  const latestEvent = w.events.at(-1);
  const caseEvent = w.events.findLast((e) => e.case_id);
  useEffect(() => {
    if (follow && caseEvent?.case_id && caseEvent.case_id !== w.caseId)
      w.select(caseEvent.case_id);
  }, [caseEvent?.event_id, follow]);
  const current = w.current;
  const tested = w.cases.filter((c) => c.paths.length).length;
  const outcomes = w.cases.map(caseOutcome);
  const counts = ["原始通过", "恢复通过", "安全停止", "待处理 / 证据不足"].map(
    (label, i) =>
      outcomes.filter((o) =>
        i === 3
          ? ["证据不足", "待处理失败"].includes(o.label)
          : o.label === label,
      ).length,
  );
  const failed = w.cases.filter((c) =>
    c.paths.some((p) => p.role === "original" && p.audit_status === "FAIL"),
  ).length;
  const checked = w.cases.filter(
    (c) => c.stopped || c.paths.at(-1)?.audit_status === "PASS",
  ).length;
  const progress = w.cases.length
    ? Math.round((100 * tested) / w.cases.length)
    : 0;
  async function work(label: string, fn: () => Promise<void>) {
    setBusy(label);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  }
  function invalidate() {
    setPlan(null);
    setError("");
  }
  async function prepare() {
    await work("plan", async () =>
      setPlan(
        await api.prepareMission({
          preset,
          config_id: config,
          max_cases: maximum,
          brief,
        }),
      ),
    );
  }
  async function generate(nextSeed = seed) {
    await work("generate", async () => {
      const value = await api.generateScene(nextSeed);
      setGenerated(value);
      setConfig(value.config_id);
      setSeed(nextSeed);
      invalidate();
    });
  }
  async function start() {
    if (!plan) return;
    await w.create({
      config_id: plan.config_id,
      mission_id: plan.mission_id,
      runtime_mode: runtime,
      execution_mode: "automatic",
      tester: runtime === "LIVE_AGNES" ? "AgnesAGH" : "AdaptiveRule",
      seed: 101,
    });
  }
  const previousRun = useRef(runId);
  useEffect(() => {
    if (runId && runId !== previousRun.current) {
      setView("run");
      setPlan(null);
    }
    previousRun.current = runId;
  }, [runId]);
  async function ask(value = question) {
    const q = value.trim();
    if (!q || !runId || busy) return;
    const epoch = requestEpoch.current;
    setQuestion("");
    setMessages((m) => [...m.slice(-18), { role: "user", text: q }]);
    await work("question", async () => {
      const answer = await api.askEvidence(runId, q);
      if (epoch === requestEpoch.current)
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            text: answer.answer,
            citations: answer.citations,
          },
        ]);
    });
  }
  async function inspect(id: string) {
    await work("evidence", async () =>
      setInspected({ id, value: await api.evidence(runId!, id) }),
    );
  }
  const openCase = (id: string) => {
    w.select(id);
    onNavigate("maps");
  };
  const citationLabel = (citation: EvidenceAnswer["citations"][number]) => {
    if (!citation.path_id) return "策略比较";
    const path = w.cases
      .find((c) => c.candidate.case_id === citation.case_id)
      ?.paths.find((p) => p.path_id === citation.path_id);
    return path?.role === "recovery"
      ? "恢复验收"
      : path?.role === "original"
        ? "原始验收"
        : "独立验收";
  };
  return (
    <div className="agent-space">
      <div className="agent-pagebar">
        <div className="agent-wordmark">
          <span className="agent-orb">
            <Bot size={21} />
          </span>
          <div>
            <strong>Agnes 测试空间</strong>
            <small>你决定验证什么，Agent 组织测试</small>
          </div>
        </div>
        <div className="agent-tabs">
          <button
            className={view === "create" ? "selected" : ""}
            onClick={() => setView("create")}
          >
            <Plus size={15} /> 新建任务
          </button>
          <button
            disabled={!w.run}
            className={view === "run" ? "selected" : ""}
            onClick={() => setView("run")}
          >
            <ActivityIcon /> 执行与发现
          </button>
        </div>
      </div>
      {error && (
        <div className="notice" role="alert">
          <TriangleAlert size={17} />
          {error}
          <button onClick={() => setError("")}>关闭</button>
        </div>
      )}
      {view === "create" ? (
        <>
          <section
            className="mission-hero"
            style={{
              backgroundImage: `url(${import.meta.env.BASE_URL}assets/mission-hero.png)`,
            }}
          >
            <div className="hero-copy">
              <div className="micro-label">
                <i /> WORLDGUARD / AUTONOMOUS TESTING
              </div>
              <h2>
                把测试交给 Agent。
                <br />
                <em>让每个结论都有依据。</em>
              </h2>
              <p>
                从一个测试目标出发，自动执行案例、检查风险、验证恢复。
                <br className="desktop-break" />
                地图、工具动作和原始失败，全程可追溯。
              </p>
              <div className="hero-proof">
                <span>
                  <CheckCheck size={14} /> 独立几何验收
                </span>
                <span>
                  <Fingerprint size={14} /> 可复现实验
                </span>
                <span>
                  <Bot size={14} /> AGH 工具闭环
                </span>
              </div>
            </div>
            <span className="concept-tag">AI 概念插画 · 非测试证据</span>
          </section>
          <div className="section-label">
            <span>01</span>
            <div>
              <h3>这次，你想验证什么？</h3>
              <p>选择一个目标即可开始准备，自然语言是可选补充。</p>
            </div>
          </div>
          <div className="mission-presets">
            {presets.map((p) => (
              <button
                key={p.id}
                className={`mission-preset ${preset === p.id ? "chosen" : ""}`}
                aria-pressed={preset === p.id}
                onClick={() => {
                  setPreset(p.id);
                  invalidate();
                }}
              >
                <div>
                  <p.icon size={21} />
                  <span>{preset === p.id ? <Check size={14} /> : p.tag}</span>
                </div>
                <strong>{p.title}</strong>
                <small>{p.subtitle}</small>
              </button>
            ))}
          </div>
          <div className="mission-setup">
            <section className="agent-card mission-input">
              <div className="card-title">
                <span className="step-dot">02</span>
                <h3>设定测试范围</h3>
                <span className="subtle">起终点与安全约束始终固定</span>
              </div>
              <div className="mission-fields">
                <label>
                  测试场景
                  <select
                    aria-label="任务测试场景"
                    value={config}
                    onChange={(e) => {
                      setConfig(e.target.value);
                      invalidate();
                    }}
                  >
                    {sceneConfigs.map((c) => (
                      <option key={c.config_id} value={c.config_id}>
                        {title(c.family)}
                      </option>
                    ))}
                    {generated && (
                      <option value={generated.config_id}>
                        生成仓库 · 种子 {generated.seed}
                      </option>
                    )}
                  </select>
                </label>
                <label>
                  最多案例数
                  <select
                    aria-label="最多案例数"
                    value={maximum}
                    onChange={(e) => {
                      setMaximum(Number(e.target.value));
                      invalidate();
                    }}
                  >
                    {[2, 3, 4, 5].map((n) => (
                      <option key={n} value={n}>
                        {n} 个案例
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  执行方式
                  <select
                    aria-label="任务执行方式"
                    value={runtime}
                    onChange={(e) =>
                      setRuntime(e.target.value as typeof runtime)
                    }
                  >
                    <option value="LIVE_AGNES" disabled={!liveAvailable}>
                      Agnes Agent · 官方 AGH
                    </option>
                    <option value="DETERMINISTIC">固定规则 · 自动对照</option>
                  </select>
                </label>
              </div>
              <div className="optional-prompt">
                <div>
                  <MessageSquare size={15} />
                  <strong>补充测试要求</strong>
                  <span>选填</span>
                </div>
                <textarea
                  aria-label="补充测试要求"
                  value={brief}
                  maxLength={1000}
                  onChange={(e) => {
                    setBrief(e.target.value);
                    invalidate();
                  }}
                  placeholder="例如：重点检查堵路后的恢复，最多 4 个案例，比较可用策略。"
                />
                <div className="prompt-footer">
                  <span>有限关键词辅助整理 · 开始前可核对计划</span>
                  <span>{brief.length}/1000</span>
                </div>
              </div>
              {w.caps && !liveAvailable && (
                <p className="inline-note">
                  <CircleHelp size={15} /> Agnes
                  当前不可用；固定规则会自动完成相同测试步骤，不产生模型调用。
                </p>
              )}
              <div className="prepare-row">
                <button
                  className="primary"
                  disabled={!!busy || w.busy || !w.connected || active}
                  onClick={() => void prepare()}
                >
                  {busy === "plan" ? (
                    <LoaderCircle className="spin" size={16} />
                  ) : (
                    <Sparkles size={16} />
                  )}{" "}
                  生成测试计划 <ArrowRight size={16} />
                </button>
              </div>
              {active && (
                <p className="inline-note">
                  当前任务仍在运行；完成或取消后再开始新任务。
                </p>
              )}
            </section>
            <section className="agent-card map-factory">
              <div className="card-title">
                <WandSparkles size={18} />
                <h3>地图工厂</h3>
                <span className="badge">PROCEDURAL</span>
              </div>
              {generated ? (
                <SceneMap
                  scene={generated.scene}
                  task={generated.task}
                  compact
                />
              ) : (
                <div className="factory-art">
                  <Box size={28} />
                  <div className="mini-racks">
                    {Array.from({ length: 12 }, (_, i) => (
                      <i key={i} />
                    ))}
                  </div>
                  <span>同一种子，重现同一座仓库</span>
                </div>
              )}
              <p>
                改变货架尺寸、分区和设备岛。生成后先验收基准路线，再用于故障测试。
              </p>
              <div className="seed-input">
                <label htmlFor="map-seed">种子</label>
                <input
                  id="map-seed"
                  type="number"
                  min={0}
                  max={2147483647}
                  value={seed}
                  onChange={(e) =>
                    setSeed(
                      Math.max(
                        0,
                        Math.min(2147483647, Number(e.target.value) || 0),
                      ),
                    )
                  }
                />
                <button
                  title="换一个种子"
                  aria-label="换一个地图种子"
                  disabled={!!busy}
                  onClick={() =>
                    void generate(
                      crypto.getRandomValues(new Uint32Array(1))[0] %
                        2147483648,
                    )
                  }
                >
                  <RefreshCw size={16} />
                </button>
                <button disabled={!!busy} onClick={() => void generate()}>
                  {busy === "generate" ? "生成中…" : "生成地图"}
                </button>
              </div>
              {generated && (
                <div className="generation-proof">
                  <CheckCheck size={14} /> 基准验收通过{" "}
                  <code>{short(generated.scene_hash)}</code>
                </div>
              )}
            </section>
          </div>
          {plan && (
            <section
              className="agent-card confirmed-plan"
              aria-label="测试计划"
            >
              <div className="card-title">
                <span className="step-dot">03</span>
                <h3>{plan.title}</h3>
                <span className="badge">待开始 · 范围已明确</span>
              </div>
              <div className="plan-split">
                <div>
                  <div className="plan-budget">
                    <span>
                      <b>{plan.max_cases}</b> 个案例
                    </span>
                    <span>
                      <b>{plan.max_actions}</b> 次导航动作上限
                    </span>
                    <span>
                      <b>{plan.compare_strategies ? "4" : "0"}</b>{" "}
                      种额外策略对比
                    </span>
                  </div>
                  <ol className="plan-steps">
                    {plan.steps.map((s, i) => (
                      <li key={s}>
                        <span>{i + 1}</span>
                        {s}
                      </li>
                    ))}
                  </ol>
                  <div className="scope-tags">
                    {plan.case_ids.map((cid) => (
                      <span key={cid}>{friendlyCase(cid)}</span>
                    ))}
                  </div>
                  {plan.notes.map((n) => (
                    <p className="plan-note" key={n}>
                      {n}
                    </p>
                  ))}
                  <p className="plan-note">{plan.limits.join(" · ")}</p>
                </div>
                <div className="plan-map">
                  <SceneMap scene={plan.scene} task={plan.task} compact />
                  <span>
                    {title(plan.family)} · {plan.scene.width} ×{" "}
                    {plan.scene.height} 网格
                  </span>
                  <code>
                    SHA {short(plan.scene_hash)} · SEED {plan.seed}
                  </code>
                </div>
              </div>
              <div className="start-row">
                <span>
                  <Bot size={16} />
                  {runtime === "LIVE_AGNES"
                    ? "Agnes 将在 AGH 中选择工具并依据验收反馈推进"
                    : "由固定规则执行 · 无模型调用"}
                </span>
                <button
                  className="primary"
                  disabled={w.busy || !!busy || active || !w.connected}
                  onClick={() => void start()}
                >
                  {w.busy ? (
                    <LoaderCircle className="spin" size={16} />
                  ) : (
                    <ArrowRight size={17} />
                  )}{" "}
                  开始自动测试
                </button>
              </div>
            </section>
          )}
        </>
      ) : w.run ? (
        <>
          <section className="mission-run-heading">
            <div>
              <div className="micro-label">
                {w.run.state.runtime_mode === "LIVE_AGNES"
                  ? "AGNES / OFFICIAL AGH"
                  : "DETERMINISTIC / RULE CONTROLLER"}
              </div>
              <h2>{mission?.title || "导航安全测试"}</h2>
              <p>
                {mission?.brief ||
                  "从基准到故障，从发现到恢复。每一步都有可核对的工具记录。"}
              </p>
            </div>
            <div className={`run-state ${active ? "running" : ""}`}>
              <i />
              {title(w.run.state.status)}
              <small>
                {w.run.state.runtime_mode === "LIVE_AGNES"
                  ? "Agnes Agent"
                  : "固定规则对照"}
              </small>
              {w.cancellable && (
                <button
                  className="cancel-agent"
                  disabled={w.busy}
                  onClick={() => void w.perform(() => api.stopRun(runId!))}
                >
                  <Square size={11} /> 取消任务
                </button>
              )}
            </div>
          </section>
          {w.run.execution_error && (
            <div className="notice" role="alert">
              <TriangleAlert size={17} />
              <span>
                执行环境异常：{w.run.execution_error.code}
                。已有结果保留，未完成部分不计为导航算法失败。
              </span>
            </div>
          )}
          <div className="run-kpis">
            {["原始通过", "恢复通过", "安全停止", "待处理 / 证据不足"].map(
              (label, i) => (
                <div key={label} className={`outcome-${i}`}>
                  <span>{label}</span>
                  <strong>{counts[i]}</strong>
                  <small>
                    {
                      [
                        "无需恢复",
                        "原始失败保留",
                        "未到达目标",
                        "未执行或未验收",
                      ][i]
                    }
                  </small>
                </div>
              ),
            )}
          </div>
          <div className="agent-execution-layout">
            <div className="execution-main">
              <section className="agent-card agent-now">
                <div className="card-title">
                  <span className={`agent-orb ${active ? "breathing" : ""}`}>
                    <Bot size={21} />
                  </span>
                  <h3>
                    {w.run.state.runtime_mode === "LIVE_AGNES"
                      ? "Agnes 执行台"
                      : "自动测试执行台"}
                  </h3>
                  <span className="subtle">
                    {active ? "正在运行" : "本次记录"}
                  </span>
                </div>
                <div className="now-line">
                  <span className="status-dot" />
                  <strong>
                    {active
                      ? eventNames[latestEvent?.tool_name || ""]?.[0] ||
                        "启动执行环境，等待工具事件"
                      : w.run.state.status === "COMPLETED"
                        ? "本轮执行结束"
                        : `本轮${title(w.run.state.status)}`}
                  </strong>
                  <span>
                    {tested}/{w.cases.length} 个案例已执行
                  </span>
                </div>
                <div className="execution-progress">
                  <i style={{ width: `${progress}%` }} />
                </div>
                <p className="now-note">
                  {active
                    ? "工具完成后更新记录；等待模型响应期间，已有证据会保留。"
                    : `发现 ${failed} 个原始失败案例；${checked} 个案例已有通过路线或停止记录。结论仅适用于本次范围。`}
                </p>
                {decisions.length > 0 ? (
                  <div className="public-decisions">
                    {decisions.map((d, i) => (
                      <article key={`${d.timestamp}-${i}`}>
                        <div>
                          <span className="decision-number">{i + 1}</span>
                          <strong>{phaseNames[d.phase] || d.phase}</strong>
                          <time>
                            {new Date(d.timestamp).toLocaleTimeString("zh-CN", {
                              hour12: false,
                            })}
                          </time>
                        </div>
                        <p>{d.summary}</p>
                        {d.case_order.length > 0 && (
                          <div className="scope-tags">
                            {d.case_order.map((cid) => (
                              <span key={cid}>{friendlyCase(cid)}</span>
                            ))}
                          </div>
                        )}
                        {d.evidence_ids.length > 0 && (
                          <div className="citation-row">
                            {d.evidence_ids.map((eid) => (
                              <button
                                key={eid}
                                onClick={() => void inspect(eid)}
                              >
                                <FileText size={12} /> 依据{" "}
                                {short(eid.replace("evidence_", ""))}
                              </button>
                            ))}
                          </div>
                        )}
                        <small>
                          {d.source === "AGNES_AGH"
                            ? "Agnes 公开行动摘要"
                            : "固定规则行动说明"}{" "}
                          · 安全结论以独立验收为准
                        </small>
                      </article>
                    ))}
                  </div>
                ) : (
                  <div className="quiet-state">
                    <Clock3 size={19} />
                    {active
                      ? "等待第一条公开行动摘要。下方工具记录会随执行更新。"
                      : "该历史任务未记录公开行动摘要，可查看下方实际工具记录。"}
                  </div>
                )}
                <details className="tool-records">
                  <summary>
                    工具调用记录 <span>{w.events.length} 条</span>
                  </summary>
                  <div>
                    {w.events.map((e) => (
                      <article key={e.event_id}>
                        <span className="tool-dot" />
                        <div>
                          <strong>
                            {eventNames[e.tool_name]?.[0] || e.tool_name}
                          </strong>
                          <small>
                            {e.tool_name}
                            {e.case_id ? ` · ${friendlyCase(e.case_id)}` : ""}
                          </small>
                        </div>
                        <time>
                          {new Date(e.timestamp).toLocaleTimeString("zh-CN", {
                            hour12: false,
                          })}
                        </time>
                      </article>
                    ))}
                  </div>
                </details>
              </section>
              <section className="agent-card findings">
                <div className="card-title">
                  <Target size={18} />
                  <h3>发现与处理</h3>
                  <span className="subtle">点击案例定位地图</span>
                </div>
                {w.cases.map((c) => {
                  const out = caseOutcome(c);
                  const origin = c.paths.find((p) => p.role === "original");
                  const recovery = c.paths
                    .filter((p) => p.role === "recovery")
                    .at(-1);
                  return (
                    <button
                      key={c.candidate.case_id}
                      className={`finding-row ${w.caseId === c.candidate.case_id ? "selected" : ""}`}
                      onClick={() => {
                        setFollow(false);
                        w.select(c.candidate.case_id);
                      }}
                    >
                      <div className={`finding-icon ${out.tone}`}>
                        {c.candidate.fault === "NONE" ? (
                          <ShieldCheck size={18} />
                        ) : (
                          <TriangleAlert size={18} />
                        )}
                      </div>
                      <div>
                        <strong>{friendlyCase(c.candidate.case_id)}</strong>
                        <small>{out.detail}</small>
                        <div className="case-chain">
                          <span>
                            原始 {title(origin?.audit_status || "NOT_RUN")}
                          </span>
                          {recovery && (
                            <>
                              <ArrowRight size={11} />
                              <span>
                                恢复 {title(recovery.audit_status || "NOT_RUN")}
                              </span>
                            </>
                          )}
                          {c.stopped && (
                            <>
                              <ArrowRight size={11} />
                              <span>停止</span>
                            </>
                          )}
                        </div>
                      </div>
                      <span className={`outcome-badge ${out.tone}`}>
                        {out.label}
                      </span>
                      <ChevronRight size={15} />
                    </button>
                  );
                })}
              </section>
              <section className="agent-card evidence-assistant">
                <div className="card-title">
                  <MessageSquare size={18} />
                  <h3>问问这次测试</h3>
                  <span className="subtle">评测 Agent · 模型解读</span>
                </div>
                <p className="assistant-intro">
                  可以追问失败原因和恢复结果。回答引用本次验收记录，不替代评测
                  Agent 的执行决策。
                </p>
                <div className="question-chips">
                  {[
                    "发现了什么问题？",
                    "恢复结果怎么样？",
                    "为什么必须停止？",
                  ].map((q) => (
                    <button
                      key={q}
                      disabled={!!busy}
                      onClick={() => void ask(q)}
                    >
                      {q}
                    </button>
                  ))}
                </div>
                <div className="chat-messages" aria-live="polite">
                  {messages.map((m, i) => (
                    <article key={i} className={`chat-${m.role}`}>
                      <span>{m.role === "user" ? "你" : "WG"}</span>
                      <div>
                        <p>{m.text}</p>
                        {m.citations && (
                          <div className="citation-row">
                            {m.citations.map((c, j) => (
                              <button
                                key={j}
                                onClick={() =>
                                  c.evidence_id
                                    ? void inspect(c.evidence_id)
                                    : openCase(c.case_id)
                                }
                              >
                                <FileText size={12} />
                                {friendlyCase(c.case_id)} · {citationLabel(c)}{" "}
                                {j + 1}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </article>
                  ))}
                  {busy === "question" && (
                    <span className="subtle">正在读取本次证据…</span>
                  )}
                  <div ref={chatEnd} />
                </div>
                <form
                  className="question-form"
                  onSubmit={(e) => {
                    e.preventDefault();
                    void ask();
                  }}
                >
                  <input
                    aria-label="向评测 Agent 提问"
                    placeholder="例如：这次堵路是怎么恢复的？"
                    maxLength={500}
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                  />
                  <button
                    className="primary"
                    aria-label="发送问题"
                    disabled={!question.trim() || !!busy}
                  >
                    <ArrowUp size={18} />
                  </button>
                </form>
              </section>
            </div>
            <aside className="execution-evidence">
              <section className="agent-card evidence-map">
                <div className="card-title">
                  <MapIcon size={18} />
                  <h3>当前测试现场</h3>
                  <button
                    className="text-button"
                    onClick={() => onNavigate("maps")}
                  >
                    展开 <ArrowRight size={13} />
                  </button>
                </div>
                {current ? (
                  <>
                    <SceneMap
                      scene={current.scene_after}
                      task={current.task}
                      before={current.scene_before}
                      paths={current.paths}
                    />
                    <div className="map-case-label">
                      <span>{friendlyCase(current.candidate.case_id)}</span>
                      <button
                        className="text-button"
                        aria-pressed={follow}
                        onClick={() => setFollow(!follow)}
                      >
                        {follow ? "已跟随执行" : "跟随执行"}
                      </button>
                    </div>
                  </>
                ) : (
                  <div className="quiet-state">正在读取地图…</div>
                )}
              </section>
              <section className="agent-card run-envelope">
                <div className="card-title">
                  <Fingerprint size={17} />
                  <h3>本轮测试边界</h3>
                </div>
                <dl>
                  <div>
                    <dt>测试员</dt>
                    <dd>
                      {w.run.state.runtime_mode === "LIVE_AGNES"
                        ? "Agnes · 官方 AGH"
                        : title(w.run.tester || "FixedCoverage")}
                    </dd>
                  </div>
                  <div>
                    <dt>导航器</dt>
                    <dd>安全 A* · 二维网格</dd>
                  </div>
                  <div>
                    <dt>案例范围</dt>
                    <dd>{w.cases.length} 个 / 单一地图</dd>
                  </div>
                  <div>
                    <dt>导航动作</dt>
                    <dd>
                      {w.run.state.sut_executions} /{" "}
                      {String(w.run.state.config.max_actions)}
                    </dd>
                  </div>
                  <div>
                    <dt>模型请求</dt>
                    <dd>{w.run.state.model_requests ?? "运行结束后统计"}</dd>
                  </div>
                  <div>
                    <dt>环境种子</dt>
                    <dd>{String(w.run.state.config.seed)}</dd>
                  </div>
                </dl>
                <code>{runId}</code>
                <p>
                  安全停止不等于到达。未测试的地图和故障，不在本次结论范围内。
                </p>
                {!!(
                  w.run.agh_session?.trace as
                    | { nonce_round_trip?: boolean }
                    | undefined
                )?.nonce_round_trip && (
                  <div className="agh-proof">
                    <CheckCheck size={15} /> 已保存 AGH 会话记录
                  </div>
                )}
              </section>
              <section className="agent-card delivery-card">
                <FileText size={24} />
                <h3>测试交付物</h3>
                <p>原始失败、恢复路径、独立验收与完整工具记录。</p>
                <button
                  disabled={!w.report}
                  onClick={() => onNavigate("reports")}
                >
                  打开复盘报告 <ArrowRight size={14} />
                </button>
                <button
                  onClick={() => {
                    const optimized = w.report?.optimizations?.[0]?.case_id;
                    if (typeof optimized === "string") w.select(optimized);
                    onNavigate("strategies");
                  }}
                >
                  查看策略对比 <Route size={14} />
                </button>
                {w.report && (
                  <a href={api.exportURL(runId!)}>
                    下载完整证据 ZIP <ArrowRight size={14} />
                  </a>
                )}
              </section>
            </aside>
          </div>
        </>
      ) : (
        <section className="agent-card quiet-state">
          还没有测试任务。
          <button onClick={() => setView("create")}>创建第一个任务</button>
        </section>
      )}
      {inspected && (
        <div
          className="evidence-dialog-backdrop"
          onClick={() => setInspected(null)}
        >
          <section
            className="evidence-dialog agent-card"
            role="dialog"
            aria-modal="true"
            aria-label="原始验收证据"
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => {
              if (e.key === "Escape") setInspected(null);
              if (e.key === "Tab") {
                e.preventDefault();
                (
                  e.currentTarget.querySelector(
                    "button",
                  ) as HTMLButtonElement | null
                )?.focus();
              }
            }}
          >
            <div className="card-title">
              <FileText size={18} />
              <h3>原始验收证据</h3>
              <button autoFocus onClick={() => setInspected(null)}>
                关闭
              </button>
            </div>
            <code>{inspected.id}</code>
            <pre>{JSON.stringify(inspected.value, null, 2)}</pre>
          </section>
        </div>
      )}
    </div>
  );
}
function ActivityIcon() {
  return (
    <span className="activity-icon">
      <i />
      <i />
      <i />
    </span>
  );
}
