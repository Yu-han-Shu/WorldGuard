import { useEffect, useRef, useState } from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  ArrowUp,
  Bot,
  Check,
  CheckCheck,
  ChevronDown,
  ChevronRight,
  Code2,
  FileCode2,
  FileText,
  FlaskConical,
  Folder,
  History,
  LoaderCircle,
  Map as MapIcon,
  Menu,
  Paperclip,
  Plus,
  ShieldCheck,
  Square,
  TriangleAlert,
  X,
  Sparkles,
  Search,
  Route,
  Play,
  Activity,
} from "lucide-react";
import { api, eventNames, title, useWorkbench } from "./useWorkbench";
import { SceneMap } from "./SceneMap";
import { CaseJourney } from "./CaseJourney";
import { ExperimentLab } from "./ExperimentLab";
import { ExecutionActivity } from "./ExecutionActivity.tsx";
import {
  caseOutcome,
  type EvidenceAnswer,
  type MissionPlan,
  type PublicDecision,
  type Submission,
} from "./missionTypes";
import "./studio.css";
import "./studio-tech.css";
import "./experiment-lab.css";
import "./visual-system.css";

type Workbench = ReturnType<typeof useWorkbench>;
type ArtifactTab = "map" | "code" | "evidence" | "report" | "lab";
const chatError = (code: string) =>
  ({
    CHAT_TIMEOUT: "模型响应超时，这次没有生成回答。可以稍后重试。",
    CHAT_AUTH: "模型连接认证失败，请检查本地模型配置后重试。",
    CHAT_RATE_LIMIT: "模型服务暂时限流，请稍后重试。",
    CHAT_MODEL_UNAVAILABLE: "当前没有可用的对话模型，请先连接本地模型服务。",
    CHAT_BUDGET_EXHAUSTED:
      "本轮对话或模型请求预算已用完。评测结果和证据仍可查看。",
    CHAT_BUSY: "还有一个模型请求正在处理，请稍后再发送。",
    CHAT_INVALID_RESPONSE:
      "模型回答或引用未通过校验，未展示未经核对的内容。可以重试。",
    CHAT_INTERRUPTED: "上次请求尚未完成或已中断，请稍后刷新记录。",
  })[code] || "模型连接失败，未生成回答。请检查服务连接后重试。";
const sample = JSON.stringify(
  {
    schema_version: "worldguard-strategy/v1",
    planner: "strategy_astar",
    turn_cost_m: 0.25,
    clearance_weight: 0,
  },
  null,
  2,
);
const caseTitle = (id: string) =>
  id === "normal"
    ? "正常通行基准"
    : title(id.replace(/_\d+$/, "").toUpperCase()) + " " + id.split("_").at(-1);
const time = (value: string) =>
  new Date(value).toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
const phases: Record<string, string> = {
  PLAN: "计划",
  FINDING: "发现",
  RECOVERY: "处理",
  COMPLETE: "结论",
};
const download = (name: string, value: string) => {
  const url = URL.createObjectURL(
    new Blob([value], { type: "text/plain;charset=utf-8" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};

function EvidenceDetail({ data }: { data: unknown }) {
  const record =
    data && typeof data === "object" ? (data as Record<string, unknown>) : {};
  const audit =
    record.audit && typeof record.audit === "object"
      ? (record.audit as Record<string, unknown>)
      : null;
  const clearance = audit?.minimum_remaining_clearance_m;
  const violations = Array.isArray(audit?.violations) ? audit.violations : [];
  return (
    <>
      {audit && (
        <div
          className={
            "studio-audit-summary " +
            (audit.status === "PASS" ? "pass" : "fail")
          }
        >
          <div>
            <ShieldCheck size={21} />
            <span>
              <b>
                {audit.status === "PASS"
                  ? "路线通过独立验收"
                  : audit.status === "FAIL"
                    ? "路线未通过独立验收"
                    : "尚无确定验收结论"}
              </b>
              <small>
                {typeof record.case_id === "string"
                  ? caseTitle(record.case_id)
                  : "当前证据"}
              </small>
            </span>
          </div>
          <dl>
            <div>
              <dt>最小剩余净空</dt>
              <dd>
                {typeof clearance === "number"
                  ? clearance.toFixed(3) + " m"
                  : "未记录"}
              </dd>
            </div>
            <div>
              <dt>违规记录</dt>
              <dd>{violations.length} 处</dd>
            </div>
          </dl>
          <p>
            {audit.status === "PASS"
              ? "本条路径满足本次地图和机器人尺寸下的验收约束。"
              : "请结合故障位置检查路径，负净空表示机器人安全范围侵入障碍。"}
          </p>
        </div>
      )}
      <details className="studio-evidence-details" open={!audit}>
        <summary>
          原始记录与校验信息
          <ChevronDown size={14} />
        </summary>
        <pre className="studio-evidence-json">
          {JSON.stringify(data, null, 2)}
        </pre>
      </details>
    </>
  );
}

export function AgentStudio({ w }: { w: Workbench }) {
  const [view, setView] = useState<"draft" | "run">(
    location.search.includes("run=") ? "run" : "draft",
  );
  const [submission, setSubmission] = useState<Submission | null>(null);
  const [brief, setBrief] = useState("");
  const [plan, setPlan] = useState<MissionPlan | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [sideOpen, setSideOpen] = useState(false);
  const [tab, setTab] = useState<ArtifactTab>("map");
  const [forcedRules, setForcedRules] = useState(false);
  const [editRequest, setEditRequest] = useState(false);
  const [previewFile, setPreviewFile] = useState(false);
  const [follow, setFollow] = useState(true);
  const [question, setQuestion] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatReady, setChatReady] = useState(false);
  const [chatLoadError, setChatLoadError] = useState(false);
  const [chatReload, setChatReload] = useState(0);
  const [messages, setMessages] = useState<
    {
      role: "user" | "assistant";
      text: string;
      citations?: EvidenceAnswer["citations"];
      failed?: boolean;
      retry?: string;
    }[]
  >([]);
  const [evidence, setEvidence] = useState<{
    id: string;
    data: unknown;
  } | null>(null);
  const upload = useRef<HTMLInputElement>(null);
  const briefInput = useRef<HTMLTextAreaElement>(null);
  const epoch = useRef(0);
  const lastRun = useRef(w.run?.state.run_id);
  const reportShownFor = useRef<string | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const activeRun = w.run?.state.run_id;
  const running = view === "run" && w.run?.state.status === "RUNNING";
  const available = w.caps?.runtime_modes.some(
    (m) => m.id === "LIVE_AGNES" && m.available,
  );
  const live = w.run?.state.runtime_mode === "LIVE_AGNES";
  const agentName = live ? "评测 Agent" : "自动测试";
  const currentSubmission =
    view === "run" ? (w.run?.submission as Submission | null) : submission;
  const currentPlan =
    view === "run" ? (w.run?.mission as MissionPlan | null) : plan;
  const decisions = (w.run?.agent_decisions || []) as PublicDecision[];
  const showArtifacts =
    view === "run" ||
    !!plan ||
    previewFile ||
    submission?.status === "STATIC_ONLY";
  const failed = w.cases.filter((c) =>
    c.paths.some((p) => p.role === "original" && p.audit_status === "FAIL"),
  ).length;
  const done = w.cases.filter((c) => c.paths.length).length;
  const lastCase = w.events.findLast((e) => e.case_id);
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [view, plan?.mission_id]);
  useEffect(() => {
    if (activeRun && activeRun !== lastRun.current) {
      setView("run");
      setPlan(null);
      setMessages([]);
      setChatOpen(false);
      setEvidence(null);
      epoch.current++;
    }
    lastRun.current = activeRun;
  }, [activeRun]);
  useEffect(() => {
    if (
      view === "run" &&
      activeRun &&
      w.run?.state.status === "COMPLETED" &&
      w.report &&
      reportShownFor.current !== activeRun
    ) {
      reportShownFor.current = activeRun;
      setTab("report");
    }
  }, [activeRun, view, w.run?.state.status, w.report]);
  useEffect(() => {
    let cancelled = false;
    setChatReady(false);
    setChatBusy(false);
    setChatLoadError(false);
    if (activeRun)
      void api
        .evidenceChat(activeRun)
        .then(({ items }) => {
          if (cancelled) return;
          setMessages(
            items.flatMap((item) => [
              { role: "user" as const, text: item.question },
              {
                role: "assistant" as const,
                text:
                  item.response?.answer ||
                  chatError(item.error_code || "CHAT_INTERRUPTED"),
                citations: item.response?.citations,
                failed: item.status !== "COMPLETED",
                retry: item.status === "ERROR" ? item.question : undefined,
              },
            ]),
          );
          setChatReady(true);
        })
        .catch(() => {
          if (!cancelled) setChatLoadError(true);
        });
    return () => {
      cancelled = true;
    };
  }, [activeRun, chatReload]);
  useEffect(() => {
    if (
      view === "run" &&
      follow &&
      lastCase?.case_id &&
      lastCase.case_id !== w.caseId
    )
      w.select(lastCase.case_id);
  }, [lastCase?.event_id, follow, view]);
  useEffect(() => {
    if (chatOpen && messages.length)
      end.current?.scrollIntoView({
        block: "nearest",
        behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "auto"
          : "smooth",
      });
  }, [messages.length, chatOpen]);
  async function action(label: string, fn: () => Promise<void>) {
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
  function newTask() {
    epoch.current++;
    reportShownFor.current = null;
    w.clear();
    setView("draft");
    setPlan(null);
    setSubmission(null);
    setBrief("");
    setMessages([]);
    setChatOpen(false);
    setEvidence(null);
    setError("");
    setFollow(true);
    setEditRequest(false);
    setPreviewFile(false);
    setSideOpen(false);
    history.replaceState(null, "", "#agent");
  }
  async function loadFile(file: File) {
    if (file.size > 64000) {
      setError("文件过大，请上传 64 KB 以内的 JSON 策略或 Python 文件。");
      return;
    }
    if (!/\.(json|py)$/.test(file.name)) {
      setError("目前支持 .json 策略和 .py 文件。");
      return;
    }
    await action("upload", async () => {
      setSubmission(await api.submitFile(file.name, await file.text()));
      setPreviewFile(false);
      setPlan(null);
      setTab("code");
    });
  }
  async function example() {
    await action("upload", async () => {
      setSubmission(await api.submitFile("warehouse_strategy.json", sample));
      setPlan(null);
      setTab("code");
    });
  }
  async function analyze() {
    const token = epoch.current;
    await action("analyze", async () => {
      const file =
        submission || (await api.submitFile("warehouse_strategy.json", sample));
      if (token !== epoch.current) return;
      setSubmission(file);
      if (file.status !== "READY") {
        setTab("code");
        return;
      }
      const scene = await api.generateScene(
        Math.floor(Math.random() * 100000),
        "v2",
      );
      const prepared = await api.prepareMission({
        preset: "comprehensive",
        config_id: scene.config_id,
        max_cases: 3,
        brief,
        submission_id: file.submission_id,
      });
      if (token === epoch.current) {
        setPlan(prepared);
        setEditRequest(false);
        setTab("map");
      }
    });
  }
  async function start() {
    if (!plan) return;
    await w.create({
      config_id: plan.config_id,
      mission_id: plan.mission_id,
      runtime_mode: available && !forcedRules ? "LIVE_AGNES" : "DETERMINISTIC",
      execution_mode: "automatic",
      tester: available && !forcedRules ? "AgnesAGH" : "AdaptiveRule",
      seed: 101,
    });
  }
  async function ask(q = question) {
    if (!activeRun || !q.trim() || chatBusy || !chatReady) return;
    const token = epoch.current;
    setChatBusy(true);
    setChatOpen(true);
    setQuestion("");
    setMessages((m) => [...m, { role: "user", text: q }]);
    try {
      const answer = await api.askEvidence(activeRun, q, w.caseId || undefined);
      if (token === epoch.current)
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            text: answer.answer,
            citations: answer.citations,
          },
        ]);
    } catch (e) {
      const code =
        e && typeof e === "object" && "code" in e ? String(e.code) : "";
      if (token === epoch.current)
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            text: chatError(code),
            failed: true,
            retry: q,
          },
        ]);
    } finally {
      if (token === epoch.current) setChatBusy(false);
    }
  }
  async function inspect(id: string) {
    if (!activeRun) return;
    const token = epoch.current;
    await action("evidence", async () => {
      const data = await api.evidence(activeRun, id);
      if (token === epoch.current) {
        setEvidence({ id, data });
        setTab("evidence");
      }
    });
  }
  function chooseCase(id: string) {
    setFollow(false);
    w.select(id);
    setTab("map");
  }
  function openHistory(id: string) {
    setView("run");
    setSideOpen(false);
    setTab("map");
    setFollow(true);
    void w.load(id);
  }

  return (
    <div
      className={
        "studio " +
        (showArtifacts ? "with-artifact " : "") +
        (view === "run" ? "is-review" : "is-draft") +
        (running ? " is-running" : "")
      }
    >
      <input
        ref={upload}
        type="file"
        accept=".json,.py"
        aria-label="上传导航方案文件"
        className="studio-file-input"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void loadFile(f);
          e.target.value = "";
        }}
      />
      {sideOpen && (
        <button
          className="studio-scrim"
          aria-label="关闭侧栏"
          onClick={() => setSideOpen(false)}
        />
      )}
      <aside className={"studio-sidebar " + (sideOpen ? "open" : "")}>
        <a
          href="#agent"
          className="studio-brand"
          aria-label="WorldGuard · 新建评测"
          onClick={(e) => {
            e.preventDefault();
            if (!busy) newTask();
          }}
        >
          <img
            src="/assets/visual-v3/wide-engineering-lockup.png"
            alt="WorldGuard"
            width="200"
            height="48"
          />
        </a>
        <button className="studio-new" onClick={newTask} disabled={!!busy}>
          <Plus size={17} />
          新建评测
        </button>
        <div className="studio-project studio-context">
          <ShieldCheck size={16} />
          <span>
            导航评测<small>策略测试与结果复核</small>
          </span>
        </div>
        {currentSubmission && (
          <div className="studio-file-section">
            <span className="studio-overline">当前文件</span>
            <button
              onClick={() => {
                setPreviewFile((open) => !open);
                setTab("code");
              }}
              title={currentSubmission.filename}
            >
              <FileCode2 size={15} />
              <span>{currentSubmission.filename}</span>
            </button>
          </div>
        )}
        <div className="studio-history">
          <div className="studio-section-label">
            <History size={14} />
            最近评测<span>{w.runTotal}</span>
          </div>
          {w.runs.slice(0, 7).map((r) => (
            <button
              key={r.state.run_id}
              className={
                view === "run" && activeRun === r.state.run_id ? "active" : ""
              }
              onClick={() => openHistory(r.state.run_id)}
              disabled={!!busy || w.loading}
            >
              <span
                className={"studio-run-dot " + r.state.status.toLowerCase()}
              />
              <span>
                {String(
                  r.mission?.title || title(String(r.state.config.family)),
                )}
                <small>
                  {r.created_at
                    ? new Date(r.created_at).toLocaleDateString("zh-CN", {
                        month: "short",
                        day: "numeric",
                      })
                    : "历史任务"}{" "}
                  · {title(r.state.status)}
                </small>
              </span>
            </button>
          ))}
          {!w.runs.length && <p>你的评测记录会留在这里。</p>}
          {w.runTotal > 7 && (
            <details className="studio-older">
              <summary>更早的记录</summary>
              {w.runs.slice(7).map((r) => (
                <button
                  key={r.state.run_id}
                  onClick={() => openHistory(r.state.run_id)}
                >
                  {r.state.run_id.slice(-8)} · {title(r.state.status)}
                </button>
              ))}
              {w.historyOffset + 30 < w.runTotal && (
                <button
                  onClick={() => void w.historyPage(w.historyOffset + 30)}
                >
                  下一页记录
                </button>
              )}
            </details>
          )}
        </div>
        <div className="studio-side-bottom">
          <div>
            <span
              className={w.connected ? "studio-online" : "studio-offline"}
            />
            {w.connected ? "本地服务已连接" : "正在连接本地服务"}
            <span>LOCAL</span>
          </div>
        </div>
      </aside>
      <main className="studio-main">
        <header className="studio-top">
          <button
            className="studio-menu"
            aria-label="打开侧栏"
            onClick={() => setSideOpen(!sideOpen)}
          >
            <Menu size={18} />
          </button>
          <span>
            导航评测
            <ChevronRight size={13} />
            <b>
              {view === "draft" ? "新任务" : currentPlan?.title || "评测记录"}
            </b>
          </span>
          <div>
            {view === "run" && w.run ? (
              <>
                <span className={"studio-state " + (running ? "running" : "")}>
                  {running && <i />}
                  {title(w.run.state.status)}
                </span>
                {!running && w.report && (
                  <a
                    className="studio-export"
                    href={api.exportURL(activeRun!)}
                    download
                  >
                    <ArrowDownToLine size={14} /> 导出证据
                  </a>
                )}
                {w.cancellable && (
                  <button
                    onClick={() =>
                      void w.perform(() => api.stopRun(activeRun!))
                    }
                    disabled={w.busy}
                  >
                    <Square size={12} />
                    停止
                  </button>
                )}
              </>
            ) : (
              <span className="studio-local">
                <Activity size={14} />
                {available
                  ? "Agent 已就绪"
                  : w.connected
                    ? "本地评测已就绪"
                    : "正在连接"}
              </span>
            )}
          </div>
        </header>
        {(error || w.error) && (
          <div className="studio-error" role="alert">
            <TriangleAlert size={16} />
            <span>{error || w.error}</span>
            <button
              aria-label="关闭错误提示"
              onClick={() => {
                setError("");
                w.dismiss();
              }}
            >
              <X size={14} />
            </button>
          </div>
        )}
        {currentPlan && (
          <details className="studio-plan-strip" key={currentPlan.mission_id}>
            <summary>
              <span className="studio-plan-strip-icon">
                <CheckCheck size={20} />
              </span>
              <span className="studio-plan-strip-title">
                <b>本轮测试计划</b>
                <small>
                  {currentPlan.case_ids.length} 个案例 · 最多{" "}
                  {currentPlan.max_actions} 次导航动作
                </small>
              </span>
              <span className="studio-plan-strip-scope">
                {title(currentPlan.family)}
                <span>独立验收 · 原始失败保留</span>
              </span>
              <span className="studio-plan-strip-progress">
                {view === "run"
                  ? `${done} / ${w.cases.length} 已执行`
                  : "等待确认"}
              </span>
              <span className="studio-plan-strip-expand">
                计划详情 <ChevronDown size={14} />
              </span>
            </summary>
            <div className="studio-plan-strip-detail">
              <div>
                <p>{currentPlan.brief || currentPlan.title}</p>
                <ol>
                  {currentPlan.steps.map((step) => (
                    <li key={step}>{step}</li>
                  ))}
                </ol>
              </div>
              <div>
                <b>本轮范围</b>
                <p>{currentPlan.case_ids.map(caseTitle).join(" / ")}</p>
                <p>场景种子 {currentPlan.seed}</p>
                <small>{currentPlan.limits.join("；")}</small>
              </div>
            </div>
          </details>
        )}
        {running && w.run && (
          <ExecutionActivity
            key={activeRun}
            run={w.run}
            events={w.events}
            decisions={decisions}
            connected={w.connected}
            onInspect={(event) => {
              if (event.case_id) chooseCase(event.case_id);
              else {
                setEvidence({ id: event.event_id, data: event });
                setTab("evidence");
              }
              requestAnimationFrame(() =>
                document.querySelector(".studio-artifact")?.scrollIntoView({
                  block: "start",
                  behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
                    ? "auto"
                    : "smooth",
                }),
              );
            }}
          />
        )}
        <div className="studio-body">
          <section
            className={
              "studio-conversation " +
              (view === "draft" && !plan ? "is-intake" : "")
            }
          >
            {view === "draft" ? (
              <>
                {!plan && (
                  <div className="studio-intro">
                    <div className="studio-intro-eyebrow">
                      <Sparkles size={15} /> 导航策略评测工作空间
                    </div>
                    <h1>
                      把导航方案交给 <em>Agent</em>
                    </h1>
                    <p>
                      提交策略，说明目标。让 Agent 安排测试，交回可验证的证据。
                    </p>
                    <div className="studio-promises">
                      <span>
                        <ShieldCheck size={16} /> 独立验收
                      </span>
                      <span>
                        <Route size={16} /> 验证故障恢复
                      </span>
                      <span>
                        <FileText size={16} /> 保留完整证据
                      </span>
                    </div>
                  </div>
                )}
                {plan && (
                  <div className="studio-request-summary">
                    <span className="studio-overline">
                      准备就绪 · 下一步开始评测
                    </span>
                    <h1>这次，我们这样测。</h1>
                    <p>{brief || "验证仓库中的基础通行与堵路恢复能力。"}</p>
                    <button onClick={() => setEditRequest(!editRequest)}>
                      <FileCode2 size={14} />
                      {submission?.filename}
                      <ChevronDown size={13} /> 修改要求
                    </button>
                  </div>
                )}
                {(!plan || editRequest) && (
                  <form
                    className={"studio-composer " + (busy ? "working" : "")}
                    onSubmit={(e) => {
                      e.preventDefault();
                      void analyze();
                    }}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      if (!busy && e.dataTransfer.files[0])
                        void loadFile(e.dataTransfer.files[0]);
                    }}
                  >
                    <div className="studio-goal-row">
                      <label
                        className="studio-field-label"
                        htmlFor="studio-assessment-goal"
                      >
                        评测目标
                      </label>
                      <div className="studio-goal-input">
                        <textarea
                          id="studio-assessment-goal"
                          ref={briefInput}
                          aria-label="评测要求"
                          value={brief}
                          maxLength={1000}
                          disabled={!!busy}
                          onChange={(e) => {
                            setBrief(e.target.value);
                            setPlan(null);
                          }}
                          placeholder="说说你想验证什么，例如：仓库配送时遇到堵路，能否安全绕行？"
                        />
                        <span className="studio-character-count">
                          {brief.length} / 1000
                        </span>
                      </div>
                    </div>
                    <div className="studio-file-row">
                      {submission ? (
                        <div className="studio-attachment">
                          <FileCode2 size={21} />
                          <span>
                            <b>{submission.filename}</b>
                            <small>
                              {submission.status === "READY"
                                ? "策略格式已检查 · 可执行评测"
                                : "Python · 仅静态检查"}
                            </small>
                          </span>
                          <button
                            type="button"
                            aria-label="移除当前文件"
                            disabled={!!busy}
                            onClick={() => {
                              setSubmission(null);
                              setPlan(null);
                            }}
                          >
                            <X size={14} />
                          </button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          className="studio-upload-hint"
                          onClick={() => upload.current?.click()}
                          disabled={!!busy}
                        >
                          <Paperclip size={16} />
                          拖入策略或代码<span>.json / .py</span>
                        </button>
                      )}
                      <button
                        className="studio-sample-button"
                        type="button"
                        onClick={() => void example()}
                        disabled={!!busy}
                      >
                        <FlaskConical size={15} /> 使用示例策略
                      </button>
                    </div>
                    <div className="studio-composer-footer">
                      <button
                        type="button"
                        className="studio-attach-button"
                        onClick={() => upload.current?.click()}
                        disabled={!!busy}
                        aria-label="选择文件"
                      >
                        <Paperclip size={17} />
                        添加文件
                      </button>
                      <span>
                        {submission
                          ? "文件保存在本地项目"
                          : "没有文件也可以直接体验"}
                      </span>
                      <button
                        className="studio-primary"
                        disabled={
                          !!busy ||
                          w.busy ||
                          !w.connected ||
                          submission?.status === "STATIC_ONLY"
                        }
                      >
                        {busy ? (
                          <>
                            <LoaderCircle className="studio-spin" size={15} />
                            {busy === "upload" ? "检查文件" : "准备计划"}
                          </>
                        ) : (
                          <>
                            <Sparkles size={15} />
                            准备测试计划
                            <ArrowRight size={16} />
                          </>
                        )}
                      </button>
                    </div>
                  </form>
                )}
                {!plan && (
                  <div className="studio-quickstart-label">
                    快捷填写要求<span>点击填入，可修改后再开始</span>
                  </div>
                )}
                {!plan && (
                  <div className="studio-quickstarts">
                    {[
                      {
                        theme: "safety",
                        name: "通行与堵路",
                        detail: "测试正常通行与故障恢复",
                        icon: ShieldCheck,
                        text: "检查复杂仓库导航安全，最多4个案例",
                      },
                      {
                        theme: "boundary",
                        name: "窄通道检查",
                        detail: "检查机器人是否挤碰障碍",
                        icon: Search,
                        text: "检查窄通道净空，最多5个案例",
                      },
                      {
                        theme: "recovery",
                        name: "堵路后绕行",
                        detail: "检查改道后能否安全到达",
                        icon: Route,
                        text: "重点验证复杂仓库堵路恢复，最多3个案例",
                      },
                    ].map((q) => (
                      <button
                        key={q.name}
                        className={"studio-quickstart " + q.theme}
                        disabled={!!busy}
                        onClick={() => {
                          setBrief(q.text);
                          briefInput.current?.focus();
                        }}
                      >
                        <span className="studio-quickstart-icon">
                          <q.icon size={23} />
                        </span>
                        <span className="studio-quickstart-copy">
                          <b>{q.name}</b>
                          <small>{q.detail}</small>
                        </span>
                        <ChevronRight size={14} />
                      </button>
                    ))}
                  </div>
                )}
                {!plan && (
                  <div className="studio-under-composer">
                    <span>第一次使用？可先载入示例策略</span>
                    <button
                      onClick={() =>
                        download("worldguard_strategy.json", sample)
                      }
                    >
                      <ArrowDownToLine size={13} />
                      JSON 模板
                    </button>
                  </div>
                )}
                {submission?.status === "STATIC_ONLY" && !plan && (
                  <div className="studio-receipt">
                    <span className="studio-step-icon">
                      <Check size={15} />
                    </span>
                    <div>
                      <h3>收到方案，先检查接入方式</h3>
                      {submission.findings.map((f, i) => (
                        <p key={i}>{f}</p>
                      ))}
                      <small>静态规则检查 · 尚未执行导航</small>
                    </div>
                  </div>
                )}
                {plan && (
                  <article className="studio-plan studio-enter">
                    <div className="studio-message-author">
                      <span className="studio-bot">
                        <Bot size={18} />
                      </span>
                      <b>评测计划已准备好</b>
                      <small>开始前可检查</small>
                    </div>
                    <p>
                      这轮使用 <b>{submission?.filename}</b>，在
                      {title(plan.family)}中执行 <b>{plan.max_cases} 个案例</b>
                      。地图与策略已固定，方便复现结果。
                    </p>
                    <ol className="studio-plan-list">
                      {plan.case_ids.map((id, i) => (
                        <li key={id}>
                          <span>{String(i + 1).padStart(2, "0")}</span>
                          <div>
                            <b>{caseTitle(id)}</b>
                            <small>
                              {id === "normal"
                                ? "验证基础通行与机器人足迹"
                                : "更新真实地图，检查原路线与恢复路线"}
                            </small>
                          </div>
                          <Check size={15} />
                        </li>
                      ))}
                    </ol>
                    <div className="studio-plan-actions">
                      <details>
                        <summary>
                          运行设置
                          <ChevronDown size={12} />
                        </summary>
                        <label>
                          <input
                            type="checkbox"
                            checked={forcedRules}
                            onChange={(e) => setForcedRules(e.target.checked)}
                          />
                          使用固定规则对照（无模型调用）
                        </label>
                        <small>
                          最多 {plan.max_actions}{" "}
                          次导航动作；单机器人二维几何评测。
                        </small>
                      </details>
                      <button
                        className="studio-primary"
                        onClick={() => void start()}
                        disabled={!!busy || w.busy}
                      >
                        {w.busy ? (
                          <LoaderCircle size={15} className="studio-spin" />
                        ) : (
                          <ArrowRight size={15} />
                        )}
                        开始自动评测
                      </button>
                    </div>
                    <details className="studio-plan-method">
                      <summary>
                        评测范围与限制 <ChevronDown size={12} />
                      </summary>
                      <p className="studio-plan-note">
                        地图由程序按种子 {plan.seed}{" "}
                        生成；场景选择按预设与关键词整理。
                        {available && !forcedRules
                          ? "评测 Agent 将执行测试并依据结果推进。"
                          : "本轮由固定规则自动执行，无模型调用。"}
                      </p>
                      {plan.notes.map((n, i) => (
                        <p key={i} className="studio-plan-note">
                          {n}
                        </p>
                      ))}
                    </details>
                  </article>
                )}
                {!plan && (
                  <div className="studio-how">
                    <span>
                      <FileCode2 size={20} />
                      <b>分析方案</b>
                      <small>检查接口与评测要求</small>
                    </span>
                    <ArrowRight size={15} />
                    <span>
                      <MapIcon size={20} />
                      <b>准备地图</b>
                      <small>生成可复现的测试场景</small>
                    </span>
                    <ArrowRight size={15} />
                    <span>
                      <Play size={20} />
                      <b>自动评测</b>
                      <small>规划、验收与恢复验证</small>
                    </span>
                    <ArrowRight size={15} />
                    <span>
                      <FileText size={20} />
                      <b>交付结论</b>
                      <small>问题、证据与改进建议</small>
                    </span>
                  </div>
                )}
              </>
            ) : w.run ? (
              <>
                <div className="studio-run-intro">
                  <span className="studio-overline">
                    {live
                      ? "AGENT WORKSPACE · 自动评测"
                      : "DETERMINISTIC · 固定规则"}
                  </span>
                  <h1>
                    {!running && w.report
                      ? failed
                        ? `发现 ${failed} 个需要关注的问题`
                        : "本轮评测已完成"
                      : currentPlan?.title || "导航方案评测"}
                  </h1>
                  <div className="studio-run-file">
                    <FileCode2 size={15} />
                    {currentSubmission?.filename || "内置参考导航器"}
                    <span>
                      已执行 {done} / {w.cases.length} 案例
                    </span>
                  </div>
                </div>
                {w.run.execution_error && (
                  <div className="studio-error">
                    <TriangleAlert size={16} />
                    执行环境异常：{w.run.execution_error.code}
                    。已保存结果，未完成部分不计为导航缺陷。
                  </div>
                )}
                {!running && w.report && (
                  <div className="studio-result-stats studio-inline-stats">
                    <div>
                      <strong>
                        {
                          w.cases.filter((c) =>
                            c.paths.some(
                              (p) =>
                                p.role === "original" &&
                                p.audit_status === "PASS",
                            ),
                          ).length
                        }
                        <small> / {w.report.executed_cases}</small>
                      </strong>
                      <span>原始通过</span>
                    </div>
                    <div>
                      <strong>
                        {
                          w.cases.filter((c) =>
                            c.paths.some(
                              (p) =>
                                p.role === "recovery" &&
                                p.audit_status === "PASS",
                            ),
                          ).length
                        }
                      </strong>
                      <span>恢复通过</span>
                    </div>
                    <div>
                      <strong>{w.report.safe_stop_count}</strong>
                      <span>安全停止</span>
                    </div>
                  </div>
                )}
                {!running && <details className="studio-execution">
                  <summary>
                    <Activity size={16} />
                    <span>执行记录</span>
                    <small>
                      {decisions.length > 0 && `${decisions.length} 个公开决策 · `}
                      {w.events.length} 条记录
                    </small>
                    <ChevronDown size={14} />
                  </summary>
                  <div className="studio-message-author">
                    <span
                      className={"studio-bot " + (running ? "pulsing" : "")}
                    >
                      <Bot size={19} />
                    </span>
                    <b>{agentName} 执行记录</b>
                    <small>{running ? "执行中" : "已归档"}</small>
                  </div>
                  <div className="studio-run-progress">
                    <i
                      style={{
                        width:
                          (w.cases.length ? (done / w.cases.length) * 100 : 0) +
                          "%",
                      }}
                    />
                  </div>
                  {decisions.map((d, i) => (
                    <article className="studio-decision" key={i}>
                      <div>
                        <span>{phases[d.phase] || d.phase}</span>
                        <time>{time(d.timestamp)}</time>
                      </div>
                      <p>{d.summary}</p>
                      {d.evidence_ids.map((id) => (
                        <button
                          className="studio-citation"
                          key={id}
                          onClick={() => void inspect(id)}
                        >
                          <FileText size={12} />
                          查看依据
                        </button>
                      ))}
                    </article>
                  ))}
                  <details className="studio-tools">
                    <summary>
                      <CheckCheck size={15} />
                      工具与任务记录<span>{w.events.length}</span>
                      <ChevronDown size={14} />
                    </summary>
                    <div>
                      {w.events.map((e) => (
                        <button
                          key={e.event_id}
                          onClick={() => {
                            if (e.case_id) chooseCase(e.case_id);
                            else {
                              setEvidence({ id: e.event_id, data: e });
                              setTab("evidence");
                            }
                          }}
                        >
                          <Check size={13} />
                          <span>
                            {eventNames[e.tool_name]?.[0] || e.tool_name}
                            <small>
                              {e.case_id ? caseTitle(e.case_id) : e.tool_name}
                            </small>
                          </span>
                          <time>{time(e.timestamp)}</time>
                        </button>
                      ))}
                    </div>
                  </details>
                  {running && (
                    <div className="studio-current">
                      <span className="studio-thinking">
                        <i />
                        <i />
                        <i />
                      </span>
                      <span>
                        测试仍在继续
                        <small>
                          {lastCase
                            ? eventNames[lastCase.tool_name]?.[0] ||
                              "正在等待下一步决策"
                            : "正在建立模型会话"}{" "}
                          · 完成后自动更新
                        </small>
                      </span>
                    </div>
                  )}
                </details>}
                <article className="studio-findings">
                  <div className="studio-section-title">
                    <h2>{running ? "当前发现" : "这轮发现了什么"}</h2>
                    <span>{failed} 个原始失败</span>
                  </div>
                  {w.cases.map((c) => {
                    const outcome = caseOutcome(c);
                    const origin = c.paths.find((p) => p.role === "original");
                    return (
                      <button
                        key={c.candidate.case_id}
                        className={
                          "studio-finding " +
                          (c.candidate.case_id === w.caseId ? "active" : "")
                        }
                        onClick={() => chooseCase(c.candidate.case_id)}
                      >
                        <span className={"studio-finding-icon " + outcome.tone}>
                          {origin?.audit_status === "FAIL" ? (
                            <TriangleAlert size={17} />
                          ) : (
                            <ShieldCheck size={17} />
                          )}
                        </span>
                        <div>
                          <b>{caseTitle(c.candidate.case_id)}</b>
                          <small>{outcome.detail}</small>
                        </div>
                        <span className={outcome.tone}>{outcome.label}</span>
                        <ChevronRight size={13} />
                      </button>
                    );
                  })}
                </article>
                {!running && w.report && (
                  <article className="studio-conclusion">
                    <h3>
                      <FileText size={17} />
                      结论与下一步
                    </h3>
                    <p>
                      已执行 {w.report.executed_cases} 个案例，
                      {w.report.reached_count} 个最终到达，
                      {w.report.safe_stop_count} 个安全停止。
                      {failed
                        ? "恢复通过仍保留原始失败，建议重点复查地图更新和路径重新验收的时机。"
                        : "结论仅覆盖本轮地图与案例，建议换一个场景继续验证。"}
                    </p>
                    {tab !== "report" && (
                      <button onClick={() => setTab("report")}>
                        打开完整报告 <ArrowRight size={14} />
                      </button>
                    )}
                    <button
                      onClick={() =>
                        document
                          .getElementById("studio-followup")
                          ?.scrollIntoView({
                            block: "start",
                            behavior: matchMedia(
                              "(prefers-reduced-motion: reduce)",
                            ).matches
                              ? "auto"
                              : "smooth",
                          })
                      }
                    >
                      询问这份报告 <ChevronDown size={14} />
                    </button>
                    <button
                      onClick={() => {
                        setFollow(false);
                        const c = w.cases.find((c) =>
                          c.paths.some(
                            (p) =>
                              p.role === "original" &&
                              p.audit_status === "FAIL",
                          ),
                        );
                        if (c) w.select(c.candidate.case_id);
                        setTab("lab");
                      }}
                    >
                      <FlaskConical size={14} /> 进入反事实实验舱
                      <ArrowRight size={14} />
                    </button>
                  </article>
                )}
              </>
            ) : (
              <div className="studio-loading">
                <LoaderCircle size={24} className="studio-spin" />
                <p>正在读取评测记录…</p>
              </div>
            )}
          </section>
          {showArtifacts && (
            <aside className="studio-artifact studio-enter">
              <header>
                <span>
                  <Folder size={15} />
                  任务材料
                </span>
                <small>{view === "run" ? "与当前记录关联" : "准备中"}</small>
              </header>
              <div
                className="studio-artifact-tabs"
                role="tablist"
                aria-label="任务材料"
              >
                {(
                  [
                    ["report", "评测报告", FileText],
                    ["map", "地图", MapIcon],
                    ["code", "方案", Code2],
                    ["evidence", "证据", ShieldCheck],
                    ["lab", "实验舱", FlaskConical],
                  ] as const
                ).map(([id, label, Icon]) => (
                  <button
                    role="tab"
                    aria-selected={tab === id}
                    aria-controls={"studio-panel-" + id}
                    key={id}
                    onClick={() => setTab(id)}
                  >
                    <Icon size={14} />
                    {label}
                  </button>
                ))}
              </div>
              <div
                className="studio-artifact-content"
                role="tabpanel"
                id={"studio-panel-" + tab}
                aria-label={
                  {
                    map: "地图",
                    code: "方案",
                    evidence: "证据",
                    report: "评测报告",
                    lab: "实验舱",
                  }[tab]
                }
              >
                {tab === "map" ? (
                  <>
                    {view === "run" && w.current ? (
                      <>
                        <div className="studio-artifact-title">
                          <div>
                            <h2>{title(String(w.run?.state.config.family))}</h2>
                            <p>{caseTitle(w.caseId)} · 二维几何仿真</p>
                          </div>
                          <button
                            aria-pressed={follow}
                            onClick={() => setFollow(!follow)}
                          >
                            {follow ? "跟随执行" : "已固定案例"}
                          </button>
                        </div>
                        <CaseJourney
                          value={w.current}
                          onEvidence={(id) => void inspect(id)}
                        />
                        <div className="studio-map-caption">
                          <span>橙色虚线 / 原始</span>
                          <span>青色实线 / 恢复</span>
                        </div>
                        <div className="studio-map-cases">
                          {w.cases.map((c) => (
                            <button
                              key={c.candidate.case_id}
                              aria-pressed={c.candidate.case_id === w.caseId}
                              onClick={() => chooseCase(c.candidate.case_id)}
                            >
                              {caseTitle(c.candidate.case_id)}
                            </button>
                          ))}
                        </div>
                      </>
                    ) : plan ? (
                      <>
                        <div className="studio-artifact-title">
                          <div>
                            <h2>{title(plan.family)}</h2>
                            <p>为本轮生成 · 布局已冻结</p>
                          </div>
                          <span className="studio-tag">Seed {plan.seed}</span>
                        </div>
                        <SceneMap scene={plan.scene} task={plan.task} />
                        <div className="studio-map-caption">
                          <span>
                            {(
                              plan.scene.width * plan.scene.resolution_m
                            ).toFixed(1)}{" "}
                            ×{" "}
                            {(
                              plan.scene.height * plan.scene.resolution_m
                            ).toFixed(1)}{" "}
                            m
                          </span>
                          <span>{plan.scene.occupied.length} 个障碍网格</span>
                        </div>
                        <p className="studio-artifact-note">
                          货架、交叉通道与备用路线来自真实网格。开始后会叠加故障区域和实际规划路径。
                        </p>
                      </>
                    ) : (
                      <div className="studio-empty-artifact">
                        <MapIcon size={31} />
                        <h3>地图将在计划准备后出现</h3>
                        <p>根据目标安排评测环境，开始前可检查。</p>
                      </div>
                    )}
                    {currentPlan && (
                      <details className="studio-binding">
                        <summary>
                          查看复现信息
                          <ChevronDown size={13} />
                        </summary>
                        <p>场景种子：{currentPlan.seed}</p>
                        <p>地图指纹：{currentPlan.scene_hash}</p>
                        <p>固定半径 0.18 m · 安全余量 0.05 m</p>
                        <p>
                          故障发生后，原始规划使用变化前的地图，恢复使用更新后的地图。
                        </p>
                      </details>
                    )}
                  </>
                ) : tab === "lab" ? (
                  view === "run" && w.current ? (
                    <ExperimentLab
                      value={w.current}
                      cases={w.cases}
                      running={!!running}
                      onCase={(id) => {
                        setFollow(false);
                        w.select(id);
                      }}
                    />
                  ) : (
                    <div className="studio-empty-artifact">
                      <FlaskConical size={31} />
                      <h3>评测后，继续做对照实验</h3>
                      <p>在同一案例验证不同干预，并检查路径的证据护照。</p>
                    </div>
                  )
                ) : tab === "code" ? (
                  <>
                    {currentSubmission ? (
                      <>
                        <div className="studio-artifact-title">
                          <div>
                            <h2>{currentSubmission.filename}</h2>
                            <p>
                              {currentSubmission.status === "READY"
                                ? currentPlan
                                  ? "真实待测策略 · 参数已绑定"
                                  : "策略配置 · 可用于评测"
                                : "仅静态检查 · 未执行代码"}
                            </p>
                          </div>
                          <button
                            aria-label="下载当前方案"
                            onClick={() =>
                              download(
                                currentSubmission.filename,
                                currentSubmission.content,
                              )
                            }
                          >
                            <ArrowDownToLine size={15} />
                          </button>
                        </div>
                        <div className="studio-code">
                          <div>
                            <span>
                              {currentSubmission.filename.endsWith(".py")
                                ? "PYTHON"
                                : "JSON"}
                            </span>
                            <span>
                              {currentSubmission.content.split("\n").length} 行
                            </span>
                          </div>
                          <pre>
                            {currentSubmission.content
                              .split("\n")
                              .map((line, i) => (
                                <div key={i}>
                                  <span>{i + 1}</span>
                                  <code>{line || " "}</code>
                                </div>
                              ))}
                          </pre>
                        </div>
                        <div className="studio-code-findings">
                          <h3>接入检查</h3>
                          {currentSubmission.findings.map((f, i) => (
                            <p key={i}>
                              <Check size={13} />
                              {f}
                            </p>
                          ))}
                          <small>规则检查，非模型代码审查</small>
                        </div>
                      </>
                    ) : (
                      <div className="studio-empty-artifact">
                        <Code2 size={30} />
                        <h3>内置参考导航器</h3>
                        <p>这条历史记录没有上传文件，待测对象为参考 A*。</p>
                      </div>
                    )}
                  </>
                ) : tab === "evidence" ? (
                  <>
                    {evidence ? (
                      <>
                        <div className="studio-artifact-title">
                          <div>
                            <h2>独立验收证据</h2>
                            <p>{evidence.id}</p>
                          </div>
                          <button
                            aria-label="下载证据 JSON"
                            onClick={() =>
                              download(
                                evidence.id + ".json",
                                JSON.stringify(evidence.data, null, 2),
                              )
                            }
                          >
                            <ArrowDownToLine size={15} />
                          </button>
                        </div>
                        <EvidenceDetail data={evidence.data} />
                      </>
                    ) : (
                      <>
                        <div className="studio-artifact-title">
                          <div>
                            <h2>独立验收记录</h2>
                            <p>点击查看原始检查结果</p>
                          </div>
                        </div>
                        {w.cases.flatMap((c) =>
                          c.paths
                            .filter((p) => p.audit?.evidence_id)
                            .map((p) => (
                              <button
                                className="studio-evidence-row"
                                key={p.path_id}
                                onClick={() =>
                                  void inspect(p.audit!.evidence_id!)
                                }
                              >
                                <FileText size={16} />
                                <span>
                                  {caseTitle(c.candidate.case_id)}
                                  <small>
                                    {p.role === "original"
                                      ? "原始路径"
                                      : "恢复 / 复测路径"}
                                  </small>
                                </span>
                                <b
                                  className={
                                    p.audit_status === "PASS" ? "green" : "red"
                                  }
                                >
                                  {title(p.audit_status || "NOT_RUN")}
                                </b>
                                <ChevronRight size={13} />
                              </button>
                            )),
                        )}
                        {!w.cases.some((c) => c.paths.some((p) => p.audit)) && (
                          <div className="studio-empty-artifact">
                            <ShieldCheck size={28} />
                            <h3>等待独立验收</h3>
                            <p>评测开始后，路径与检查结果会保存在这里。</p>
                          </div>
                        )}
                      </>
                    )}
                  </>
                ) : (
                  <>
                    {w.report && view === "run" ? (
                      <>
                        <div className="studio-artifact-title">
                          <div>
                            <h2>评测报告</h2>
                            <p>{title(w.report.verdict)}</p>
                          </div>
                          <span className="studio-tag">已保存</span>
                        </div>
                        <p className="studio-artifact-note">
                          已执行 {w.report.executed_cases} 个案例 · {failed}{" "}
                          个原始失败证据已保留。
                        </p>
                        {w.current && (
                          <>
                            <h3 className="studio-compare-title">
                              {caseTitle(w.caseId)} · 原始与恢复对照
                            </h3>
                            <CaseJourney
                              value={w.current}
                              comparison
                              onEvidence={(id) => void inspect(id)}
                            />
                          </>
                        )}
                        <h3>可带走的交付物</h3>
                        <a
                          className="studio-download"
                          href={api.markdownURL(activeRun!)}
                          download
                        >
                          <FileText size={19} />
                          <span>
                            评测报告
                            <small>结论、原始失败与恢复结果 · Markdown</small>
                          </span>
                          <ArrowDownToLine size={16} />
                        </a>
                        <a
                          className="studio-download"
                          href={api.exportURL(activeRun!)}
                          download
                        >
                          <Folder size={19} />
                          <span>
                            完整证据包
                            <small>
                              方案、地图、路径、审计和工具记录 · ZIP
                            </small>
                          </span>
                          <ArrowDownToLine size={16} />
                        </a>
                        {(w.report.optimizations || []).length > 0 && (
                          <div className="studio-comparisons">
                            <h3>候选策略对比</h3>
                            {(w.report.optimizations || []).map((o, i) => (
                              <div key={i}>
                                <b>
                                  {caseTitle(String(o.case_id))} ·{" "}
                                  {title(String(o.decision))}
                                </b>
                                <p>
                                  候选方案：
                                  {title(String(o.selected_profile || "无"))}
                                </p>
                                <small>
                                  仅为该地图上的路线比较，未修改上传代码，也未替换原策略。
                                </small>
                              </div>
                            ))}
                          </div>
                        )}
                        <div className="studio-binding">
                          <p>
                            执行方式：{live ? "真实模型" : "固定规则"} ·
                            评测请求{" "}
                            {w.run?.state.model_requests ?? "未完成统计"}
                          </p>
                          <p>AGH 为执行框架。独立验收器给出路径结论。</p>
                          <p>{activeRun}</p>
                        </div>
                      </>
                    ) : (
                      <div className="studio-empty-artifact">
                        <FileText size={30} />
                        <h3>结果会在评测后交付</h3>
                        <p>
                          测了什么、发现什么、如何恢复，以及仍未验证的部分。
                        </p>
                      </div>
                    )}
                  </>
                )}
              </div>
            </aside>
          )}
        </div>
        {view === "run" && w.run && (
          <div className="studio-chat" id="studio-followup">
            <div className="studio-chat-label">
              <span className="studio-chat-identity">
                <Sparkles size={16} /> 继续讨论这份报告
              </span>
              <span>解释结果、查看依据，或讨论下一轮测试</span>
              <button
                type="button"
                className="studio-chat-toggle"
                aria-expanded={chatOpen}
                aria-controls="studio-chat-history"
                onClick={() => setChatOpen(!chatOpen)}
              >
                <History size={14} /> 对话记录{" "}
                {messages.length > 0 && (
                  <small>{Math.ceil(messages.length / 2)}</small>
                )}
                <ChevronDown size={14} />
              </button>
            </div>
            <div className="studio-suggestions">
              {["为什么失败？", "恢复结果怎么样？"].map((q) => (
                <button
                  disabled={chatBusy || !chatReady}
                  key={q}
                  onClick={() => void ask(q)}
                >
                  {q}
                  <ArrowUp size={12} />
                </button>
              ))}
            </div>
            {chatOpen && (
              <div
                className="studio-chat-history"
                id="studio-chat-history"
                role="region"
                aria-label="对话记录"
              >
                {!messages.length && !chatBusy && !chatLoadError && (
                  <p className="studio-chat-empty">
                    还没有对话。可以询问本轮结果，回答会引用实际评测记录。
                  </p>
                )}
                {messages.map((m, i) => (
                  <article
                    key={i}
                    className={
                      "studio-chat-message " +
                      m.role +
                      (m.failed ? " is-error" : "")
                    }
                  >
                    <span>
                      {m.role === "user"
                        ? "你"
                        : m.failed
                          ? "连接提示"
                          : "评测 Agent · 模型回答"}
                    </span>
                    <p>{m.text}</p>
                    {m.retry && (
                      <button
                        className="studio-chat-retry"
                        disabled={chatBusy || !chatReady}
                        onClick={() => void ask(m.retry)}
                      >
                        重新发送
                      </button>
                    )}
                    {m.citations?.map((c, j) => (
                      <button
                        key={j}
                        className="studio-citation"
                        onClick={() =>
                          c.evidence_id
                            ? void inspect(c.evidence_id)
                            : chooseCase(c.case_id)
                        }
                      >
                        <FileText size={12} />
                        {caseTitle(c.case_id)} · 证据 {j + 1}
                      </button>
                    ))}
                  </article>
                ))}
                {chatBusy && (
                  <div className="studio-chat-pending" role="status">
                    <LoaderCircle size={15} className="studio-spin" />
                    正在读取本轮证据并生成回答…
                  </div>
                )}
                {chatLoadError && (
                  <div className="studio-chat-pending" role="alert">
                    对话记录读取失败。
                    <button onClick={() => setChatReload((n) => n + 1)}>
                      重新连接
                    </button>
                  </div>
                )}
                <div ref={end} />
              </div>
            )}
            {!chatOpen && chatLoadError && (
              <p role="alert" className="studio-chat-load-error">
                对话记录读取失败。
                <button onClick={() => setChatReload((n) => n + 1)}>
                  重新连接
                </button>
              </p>
            )}
            <form
              className="studio-question"
              onSubmit={(e) => {
                e.preventDefault();
                void ask();
              }}
            >
              <input
                aria-label="向评测 Agent 提问"
                maxLength={500}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="问结果、原因，或讨论下一步…"
              />
              <button
                className="studio-primary"
                aria-label="发送问题"
                disabled={chatBusy || !chatReady || !question.trim()}
              >
                {chatBusy ? (
                  <LoaderCircle size={16} className="studio-spin" />
                ) : (
                  <ArrowUp size={17} />
                )}
              </button>
            </form>
          </div>
        )}
      </main>
    </div>
  );
}
