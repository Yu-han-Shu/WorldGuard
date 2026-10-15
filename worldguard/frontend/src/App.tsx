import { useEffect, useState, type ReactNode } from "react";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  Bot,
  Box,
  Check,
  CheckCheck,
  ChevronRight,
  CircleHelp,
  Clock3,
  FileArchive,
  FileText,
  FlaskConical,
  FolderClock,
  Gauge,
  Map as MapIcon,
  Play,
  Radar,
  RefreshCw,
  Route,
  Search,
  Settings2,
  ShieldCheck,
  ShieldAlert,
  Square,
  Target,
  TriangleAlert,
  X,
  Zap,
} from "lucide-react";
import { api, eventNames, title, useWorkbench } from "./useWorkbench";
import { SceneMap } from "./SceneMap";
import { RouteDetails, StrategyComparison } from "./AnalysisViews";
import { AgentStudio } from "./AgentStudio";
import sceneData from "./data/scenes.json";
import type { components } from "../schema";
import type { Case } from "../client";

type S = components["schemas"];
type Page =
  | "agent"
  | "workspace"
  | "scenes"
  | "maps"
  | "strategies"
  | "tasks"
  | "risk"
  | "reports";
const pageNames: Record<Page, string> = {
  agent: "Agent 测试空间",
  workspace: "高级调试工作台",
  scenes: "测试配置 / 场景库",
  maps: "地图与路径详情",
  strategies: "策略优化与方案对比",
  tasks: "任务记录",
  risk: "风险分析 / 热区洞察",
  reports: "测试复盘报告",
};
const previews = sceneData as unknown as Record<
  string,
  { scene: S["SceneView"]; task: S["TaskView"] }
>;
const pct = (a: number, b: number) => (b ? Math.round((a / b) * 100) : 0);
const num = (n: unknown, d = 2) =>
  typeof n === "number" && Number.isFinite(n) ? n.toFixed(d) : "—";
const duration = (n: number | null) =>
  n === null
    ? "—"
    : `${Math.floor(n / 60)
        .toString()
        .padStart(2, "0")}:${Math.floor(n % 60)
        .toString()
        .padStart(2, "0")}`;
const caseName = (c: Case) =>
  c.candidate.fault === "NONE"
    ? "正常基准"
    : `${title(c.candidate.fault)} · ${c.candidate.severity}`;
function Panel({
  name,
  icon,
  children,
  action,
  className = "",
}: {
  name: string;
  icon?: ReactNode;
  children: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-head">
        <h2>
          {icon || <ShieldCheck size={18} />} {name}
        </h2>
        {action}
      </div>
      {children}
    </section>
  );
}
function Stat({
  name,
  value,
  sub,
  color = "blue",
  percent = 0,
  icon,
}: {
  name: string;
  value: ReactNode;
  sub: string;
  color?: string;
  percent?: number;
  icon: ReactNode;
}) {
  return (
    <div className={`stat ${color}`}>
      <div>
        {icon}
        <span>{name}</span>
      </div>
      <strong>{value}</strong>
      <small>{sub}</small>
      <div className="meter">
        <i style={{ width: `${Math.min(100, percent)}%` }} />
      </div>
    </div>
  );
}
export default function App() {
  const w = useWorkbench();
  const [page, setPage] = useState<Page>(() => {
    const p = location.hash.slice(1);
    return p in pageNames ? (p as Page) : "agent";
  });
  const [configId, setConfigId] = useState("fulfillment_stale"),
    [tester, setTester] = useState("FixedCoverage"),
    [mode, setMode] = useState<"manual" | "automatic">("automatic"),
    [runtime, setRuntime] = useState<"DETERMINISTIC" | "LIVE_AGNES">(
      "DETERMINISTIC",
    );
  const [filter, setFilter] = useState("all"),
    [query, setQuery] = useState(""),
    [action, setAction] = useState<"REFRESH_MAP_REPLAN" | "SAFE_STOP">(
      "REFRESH_MAP_REPLAN",
    ),
    [riskLayer, setRiskLayer] = useState(false);
  const [prepared, setPrepared] = useState(false);
  const [historyStatus, setHistoryStatus] = useState("all");
  const visibleRuns = w.runs.filter(
    (r) =>
      (historyStatus === "all" || r.state.status === historyStatus) &&
      `${r.state.run_id} ${r.config_id} ${title(String(r.state.config.family || ""))} ${r.tester} ${title(r.tester || "")}`
        .toLowerCase()
        .includes(query.trim().toLowerCase()),
  );
  function navigate(p: Page) {
    setPage(p);
    history.replaceState(null, "", `${location.search}#${p}`);
  }
  useEffect(() => {
    const h = () => {
      const p = location.hash.slice(1);
      if (p in pageNames) setPage(p as Page);
    };
    window.addEventListener("hashchange", h);
    return () => window.removeEventListener("hashchange", h);
  }, []);
  useEffect(() => {
    if (w.configs.length && !w.configs.some((c) => c.config_id === configId))
      setConfigId(w.configs[0].config_id);
  }, [w.configs, configId]);
  useEffect(() => {
    if (w.run?.config_id) {
      setConfigId(w.run.config_id);
      setRuntime(w.run.state.runtime_mode);
      if (w.run.tester !== "AgnesAGH")
        setTester(w.run.tester || "FixedCoverage");
      setMode(w.run.execution_mode === "manual" ? "manual" : "automatic");
      setPrepared(false);
    }
  }, [w.run?.state.run_id]);
  const chosen = w.configs.find((c) => c.config_id === configId);
  const preview =
    previews[`${chosen?.family || "warehouse"}_${chosen?.seed || 11}`] ||
    (w.current && configId === w.run?.config_id
      ? { scene: w.current.scene_before, task: w.current.task }
      : previews.warehouse_11);
  const c = w.current,
    id = w.run?.state.run_id,
    paths = c?.paths || [];
  const allPaths = w.cases.flatMap((c) => c.paths),
    passed = allPaths.filter((p) => p.audit_status === "PASS").length,
    failed = allPaths.filter((p) => p.audit_status === "FAIL").length;
  const tested = w.cases.filter((c) => c.paths.length).length,
    stopped = w.cases.filter((c) => c.stopped).length;
  const violations = allPaths.flatMap((p) => p.audit?.audit.violations || []);
  const latest = paths.at(-1),
    recovered = latest?.role === "recovery" && latest.audit_status === "PASS";
  const verdict = c?.stopped
    ? "安全停止 · 未到达目标"
    : recovered
      ? "恢复路线已通过"
      : latest?.audit_status === "PASS"
        ? "当前路线审计通过"
        : latest?.audit_status === "FAIL"
          ? "发现路径安全问题"
          : latest
            ? "等待独立审计"
            : "等待执行案例";
  const audited =
    passed +
    failed +
    allPaths.filter((p) => p.audit_status === "UNKNOWN").length;
  const evidence = paths
    .filter((p) => p.audit && p.audit_status !== "PASS")
    .at(-1)?.audit?.evidence_id;
  const maxActions = Number(
    w.run?.state.config.max_actions || chosen?.max_actions || 12,
  );
  const liveAvailable = w.caps?.runtime_modes.some(
    (m) => m.id === "LIVE_AGNES" && m.available,
  );
  const configOptions = w.configs.filter(
    (x) => x.stale_view === (chosen?.stale_view ?? true),
  );
  const familyCards = [...new Set(configOptions.map((x) => x.family))]
    .sort(
      (a, b) =>
        Number(["fulfillment", "sorting", "terminal"].includes(b)) -
        Number(["fulfillment", "sorting", "terminal"].includes(a)),
    )
    .map(
      (family) =>
        configOptions.find(
          (x) =>
            x.family === family &&
            x.seed === (chosen?.family === family ? chosen.seed : 11),
        )!,
    )
    .filter(Boolean);
  const canCreate =
    w.connected &&
    !w.busy &&
    !!chosen &&
    !(runtime === "LIVE_AGNES" && !liveAvailable);
  function start() {
    setPrepared(false);
    navigate("workspace");
    void w.create({
      config_id: configId,
      tester: (runtime === "LIVE_AGNES"
        ? "AgnesAGH"
        : tester) as S["CreateRun"]["tester"],
      runtime_mode: runtime,
      execution_mode: runtime === "LIVE_AGNES" ? "automatic" : mode,
    });
  }
  function selectConfig(value: string) {
    setConfigId(value);
    setPrepared(true);
  }
  const mapCase = !prepared && c ? c : null;
  const mapScene = mapCase?.scene_after || preview.scene,
    mapTask = mapCase?.task || preview.task;
  const modeLabel =
    w.run?.state.runtime_mode === "LIVE_AGNES" ? "LIVE Agnes" : "确定性测试";
  const exportLinks = (
    <div className="actions">
      <a
        className={`button ${w.run?.report_available ? "" : "disabled"}`}
        aria-disabled={!w.run?.report_available}
        href={w.run?.report_available ? api.markdownURL(id!) : undefined}
        download
      >
        <FileText size={15} />
        下载报告
      </a>
      <a
        className={`button primary ${w.run?.report_available ? "" : "disabled"}`}
        aria-disabled={!w.run?.report_available}
        href={w.run?.report_available ? api.exportURL(id!) : undefined}
        download
      >
        <ArrowDownToLine size={15} />
        证据 ZIP
      </a>
    </div>
  );
  const timeline = (
    <div className="timeline" data-testid="events">
      {w.events.length ? (
        w.events
          .slice()
          .reverse()
          .map((e) => (
            <div className="timeline-item" key={e.event_id}>
              <span
                className={`event-dot ${e.status === "COMPLETED" ? "green" : ""}`}
              />
              <div>
                <div>
                  <strong>{eventNames[e.tool_name]?.[0] || e.tool_name}</strong>
                  <time>
                    {new Date(e.timestamp).toLocaleTimeString("zh-CN", {
                      hour12: false,
                    })}
                  </time>
                </div>
                <p>{eventNames[e.tool_name]?.[1] || "工具执行记录"}</p>
                <small>
                  {e.case_id || "运行级操作"} · <code>{e.tool_name}</code>
                </small>
              </div>
            </div>
          ))
      ) : (
        <div className="empty compact-empty">
          <Activity />
          <p>开始测试后展示真实工具调用</p>
        </div>
      )}
    </div>
  );
  const settings = (
    <>
      <div className="config-step">
        <span>1</span>
        <h3>测试场景</h3>
        <button className="text-button" onClick={() => navigate("scenes")}>
          场景库 <ChevronRight size={12} />
        </button>
      </div>
      <label className="sr-only" htmlFor="config">
        场景配置
      </label>
      <select
        id="config"
        value={configId}
        onChange={(e) => selectConfig(e.target.value)}
      >
        {w.configs.map((x) => (
          <option value={x.config_id} key={x.config_id}>
            {title(x.family)} · {x.seed} · {x.stale_view ? "陈旧" : "当前"}
          </option>
        ))}
      </select>
      <div className="config-preview">
        <SceneMap scene={preview.scene} task={preview.task} compact />
      </div>
      <div className="facts">
        <span>
          场景尺寸
          <b>
            {num(preview.scene.width * preview.scene.resolution_m, 1)} ×{" "}
            {num(preview.scene.height * preview.scene.resolution_m, 1)} m
          </b>
        </span>
        <span>
          网格精度<b>{preview.scene.resolution_m} m</b>
        </span>
      </div>
      <div className="config-step">
        <span>2</span>
        <h3>测试方式</h3>
      </div>
      <label>
        运行环境
        <select
          aria-label="运行环境"
          value={runtime}
          onChange={(e) => {
            const v = e.target.value as typeof runtime;
            setRuntime(v);
            if (v === "LIVE_AGNES") setMode("automatic");
          }}
        >
          <option value="DETERMINISTIC">确定性 · 无模型调用</option>
          <option value="LIVE_AGNES" disabled={!liveAvailable}>
            LIVE Agnes{liveAvailable ? "" : " · 未开放"}
          </option>
        </select>
      </label>
      <label>
        测试员
        <select
          aria-label="测试员"
          value={runtime === "LIVE_AGNES" ? "AgnesAGH" : tester}
          disabled={runtime === "LIVE_AGNES"}
          onChange={(e) => setTester(e.target.value)}
        >
          {(runtime === "LIVE_AGNES"
            ? ["AgnesAGH"]
            : w.caps?.testers.filter((t) => t !== "AgnesAGH") || []
          ).map((t) => (
            <option key={t} value={t}>
              {title(t)}
            </option>
          ))}
        </select>
      </label>
      <div className="segmented" role="group" aria-label="执行模式">
        {(["automatic", "manual"] as const).map((m) => (
          <button
            key={m}
            disabled={runtime === "LIVE_AGNES" && m === "manual"}
            aria-pressed={mode === m}
            onClick={() => setMode(m)}
          >
            {m === "automatic" ? "自动执行" : "手动调试"}
          </button>
        ))}
      </div>
      <div className="config-step">
        <span>3</span>
        <h3>机器人与预算</h3>
      </div>
      <div className="facts">
        <span>
          圆形机器人半径<b>{num(preview.task.robot.radius_m)} m</b>
        </span>
        <span>
          安全余量<b>{num(preview.task.robot.clearance_margin_m)} m</b>
        </span>
        <span>
          动作预算<b>{chosen?.max_actions ?? "—"} 次</b>
        </span>
        <span>
          最长执行时间<b>{chosen?.max_seconds ?? "—"} s</b>
        </span>
      </div>
      <p className="muted micro">使用已批准的固定参数 · 单机器人二维仿真</p>
      <button
        className="primary start-button"
        disabled={!canCreate}
        onClick={start}
      >
        <Play size={19} fill="currentColor" />
        开始测试{" "}
        <small>
          {runtime === "LIVE_AGNES"
            ? "由 Agnes 编排工具调用"
            : "运行真实规划与独立审计"}
        </small>
      </button>
    </>
  );
  const metrics = (
    <div className="stats-grid">
      <Stat
        name="案例执行覆盖"
        value={`${pct(tested, w.cases.length)}%`}
        sub={`${tested} / ${w.cases.length} 个案例已执行`}
        percent={pct(tested, w.cases.length)}
        icon={<Target />}
      />
      <Stat
        name="路径审计通过"
        value={passed}
        sub={`${audited} 条已审计路径 · 含恢复路径`}
        percent={pct(passed, audited)}
        color="green"
        icon={<ShieldCheck />}
      />
      <Stat
        name="失败路径保留"
        value={failed}
        sub="失败路径不会被恢复结果覆盖"
        percent={pct(failed, audited)}
        color="red"
        icon={<ShieldAlert />}
      />
      <Stat
        name="运行耗时"
        value={
          <>
            {duration(w.elapsed)}
            <em> min:s</em>
          </>
        }
        sub={
          w.run?.state.status === "RUNNING"
            ? "任务进行中"
            : "依据首末事件时间计算"
        }
        percent={
          w.run
            ? Math.min(
                100,
                ((w.elapsed || 0) / Number(w.run.state.config.max_seconds)) *
                  100,
              )
            : 0
        }
        color="purple"
        icon={<Clock3 />}
      />
    </div>
  );
  const auditPanel = (
    <Panel name="独立验收与恢复" icon={<ShieldCheck />}>
      <div
        className={`verdict ${c?.stopped ? "amber" : latest?.audit_status === "PASS" ? "green" : latest?.audit_status === "FAIL" ? "red" : ""}`}
      >
        <ShieldCheck size={29} />
        <div>
          <strong>{verdict}</strong>
          <p>
            {recovered
              ? "已绕开故障，原始失败证据仍保留。"
              : "结论仅适用于当前仿真地图与固定机器人。"}
          </p>
        </div>
      </div>
      <div className="path-list" data-testid="audit-results">
        {paths.map((p) => (
          <article
            className={`path-row ${p.audit_status === "FAIL" ? "mismatch" : ""}`}
            key={p.path_id}
          >
            <div>
              <strong>
                {p.role === "original"
                  ? "原始路径"
                  : p.role === "recovery"
                    ? "恢复路径"
                    : "复测路径"}
              </strong>
              <span
                className={`badge ${p.audit_status === "PASS" ? "green" : p.audit_status === "FAIL" ? "red" : ""}`}
              >
                {title(p.audit_status || "NOT_RUN")}
              </span>
            </div>
            <p>
              规划：{title(p.plan.code)} · 审计：
              {title(p.audit_status || "NOT_RUN")}
            </p>
            {p.audit && (
              <small>
                {p.audit.audit.violations.length} 处违规 · 最小剩余净空{" "}
                {num(p.audit.audit.minimum_remaining_clearance_m)} m
              </small>
            )}
            {p.audit_status === "NOT_RUN" && (
              <button
                disabled={!w.writable || w.busy}
                onClick={() =>
                  void w.perform(() => api.auditPath(id!, w.caseId, p.path_id))
                }
              >
                <ShieldCheck size={14} />
                审计此路径
              </button>
            )}
          </article>
        ))}
        {!paths.length && (
          <p className="muted">执行案例后显示路径与独立审计结论。</p>
        )}
      </div>
      {w.writable && (
        <div className="recovery">
          <label>
            恢复动作
            <select
              aria-label="恢复动作"
              value={action}
              onChange={(e) => setAction(e.target.value as typeof action)}
            >
              <option value="REFRESH_MAP_REPLAN">更新地图并重新规划</option>
              <option value="SAFE_STOP">安全停止</option>
            </select>
          </label>
          <button
            className="primary"
            disabled={w.busy || !evidence || c?.stopped}
            onClick={() =>
              void w.perform(() =>
                api.recoverCase(id!, w.caseId, {
                  action,
                  evidence_ids: [evidence!],
                  request_id: crypto.randomUUID(),
                }),
              )
            }
          >
            <RefreshCw size={14} />
            执行恢复
          </button>
        </div>
      )}
    </Panel>
  );
  if (page === "agent") return <AgentStudio w={w} />;
  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-icon">
            <ShieldCheck size={33} />
          </span>
          <strong>
            World<span>Guard</span>
          </strong>
        </div>
        <div className="brand-subtitle">
          <b>机器人 AI 安全测试工作台</b>
          <span>导航故障测试 · 独立验收 · 全程可追溯</span>
        </div>
        <div className="topbar-spacer" />
        <button
          aria-label="查找任务"
          className="search-button"
          onClick={() => navigate("tasks")}
        >
          <Search size={16} />
          <span>查找测试任务、场景、报告…</span>
          <kbd>⌕</kbd>
        </button>
        <span className={`connection ${w.connected ? "online" : ""}`}>
          <i />
          {w.connected ? "服务已连接" : "连接中"}
        </span>
        <details className="workspace-info">
          <summary>
            <Bot size={17} />
            <span>本地工作区</span>
          </summary>
          <div>
            <b>WorldGuard · 本机工作区</b>
            <p>当前为本地单用户工作台，没有登录账号。</p>
            <p>测试记录保存在后端运行目录，可通过任务记录查看与导出。</p>
            <span className="badge">
              {w.connected ? "API 已连接" : "API 未连接"}
            </span>
          </div>
        </details>
      </header>
      <div className="app-body">
        <aside className="navigation">
          <div className="nav-caption">WORKSPACE</div>
          {(
            [
              ["agent", Bot, "Agent 测试空间"],
              ["scenes", Settings2, "测试配置"],
              ["maps", MapIcon, "地图与路径"],
              ["strategies", Route, "策略优化"],
              ["tasks", FolderClock, "任务记录"],
              ["risk", Radar, "风险分析"],
              ["reports", FileText, "报告中心"],
            ] as const
          ).map(([key, Icon, text]) => (
            <button
              key={key}
              aria-label={text}
              title={text}
              className={page === key ? "active" : ""}
              aria-current={page === key ? "page" : undefined}
              onClick={() => navigate(key)}
            >
              <Icon size={19} />
              <span>{text}</span>
              {page === key && <i />}
            </button>
          ))}
          <div className="nav-bottom">
            <svg
              className="robot-art"
              viewBox="715 300 410 290"
              role="img"
              aria-label="WorldGuard 仿真机器人概念形象"
            >
              <image
                href={`${import.meta.env.BASE_URL}assets/worldguard-robots.png`}
                width="1448"
                height="1086"
              />
            </svg>
            <span>WORLDGUARD</span>
            <small>导航测试 · 仿真验证</small>
            <div className="version">
              AGENT WORKSPACE <b>04</b>
            </div>
          </div>
        </aside>
        <main>
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                WORLDGUARD <ChevronRight size={11} />{" "}
                {page === "workspace" ? "MISSION CONTROL" : page.toUpperCase()}
              </div>
              <h1>
                {pageNames[page]} <span className="badge">{modeLabel}</span>
              </h1>
            </div>
            <div className="actions">
              {w.run && (
                <button
                  aria-label="刷新运行"
                  onClick={() => void w.refresh()}
                  disabled={w.busy}
                >
                  <RefreshCw size={15} />
                  <span>刷新</span>
                </button>
              )}
              {page === "reports"
                ? exportLinks
                : w.run && (
                    <>
                      <span
                        className={`badge ${w.run.state.status === "COMPLETED" ? "green" : ""}`}
                      >
                        {title(w.run.state.status)}
                      </span>
                      <button
                        className="danger"
                        disabled={!w.cancellable || w.busy}
                        onClick={() => void w.perform(() => api.stopRun(id!))}
                      >
                        <Square size={13} />
                        取消任务
                      </button>
                    </>
                  )}
            </div>
          </div>
          {w.error && (
            <div className="notice" role="alert">
              <TriangleAlert size={18} />
              <span>{w.error}</span>
              <button onClick={w.dismiss} aria-label="关闭提示">
                <X size={16} />
              </button>
            </div>
          )}
          {w.loading && (
            <div className="loading-bar" role="status">
              正在读取真实运行记录…
            </div>
          )}
          {page === "workspace" && (
            <>
              <div className="dashboard">
                <Panel
                  name="测试配置"
                  icon={<Settings2 />}
                  className="configuration-panel"
                >
                  <div className="config-body">{settings}</div>
                </Panel>
                <div className="map-column">
                  <Panel
                    name="场景地图与路径规划"
                    icon={<MapIcon />}
                    action={
                      <div className="segmented small">
                        <button
                          aria-pressed={!riskLayer}
                          onClick={() => setRiskLayer(false)}
                        >
                          2D 俯视图
                        </button>
                        <button
                          aria-pressed={riskLayer}
                          onClick={() => setRiskLayer(true)}
                        >
                          风险叠加
                        </button>
                      </div>
                    }
                  >
                    <div className="map-subhead">
                      <span>
                        {title(
                          mapScene.scene_id.split("_").slice(0, -1).join("_"),
                        )}{" "}
                        <b>{mapScene.scene_id}</b>
                      </span>
                      <span>
                        {mapCase
                          ? `${caseName(mapCase)} · 运行地图`
                          : "场景预览 · 尚未执行"}
                      </span>
                    </div>
                    <SceneMap
                      scene={mapScene}
                      task={mapTask}
                      before={mapCase?.scene_before}
                      paths={mapCase?.paths}
                      risk={riskLayer}
                    />
                    <div className="map-detail-link">
                      <span>点击地图元素可查看尺寸 · 拖动平移</span>
                      <button
                        className="text-button"
                        onClick={() => navigate("maps")}
                      >
                        打开路径回放 <ArrowRight size={14} />
                      </button>
                    </div>
                  </Panel>
                  <Panel
                    name="测试案例"
                    icon={<FlaskConical />}
                    action={
                      <span className="muted">{w.cases.length} 个候选</span>
                    }
                  >
                    <div className="case-tabs" data-testid="candidates">
                      {w.cases.map((x) => (
                        <button
                          className={
                            w.caseId === x.candidate.case_id ? "selected" : ""
                          }
                          key={x.candidate.case_id}
                          onClick={() => {
                            setPrepared(false);
                            w.select(x.candidate.case_id);
                          }}
                        >
                          <span
                            className={`dot ${x.stopped ? "amber" : x.paths.at(-1)?.audit_status === "PASS" ? "green" : x.paths.some((p) => p.audit_status === "FAIL") ? "red" : ""}`}
                          />
                          {caseName(x)}
                          <small>{x.candidate.case_id}</small>
                        </button>
                      ))}
                      {!w.cases.length && (
                        <p className="muted">
                          选择场景并开始测试，或从任务记录打开已有结果。
                        </p>
                      )}
                    </div>
                    <div className="case-actions">
                      <span>
                        {w.run?.job_active
                          ? "测试员正在自动执行"
                          : w.run
                            ? `${w.run.execution_mode === "manual" ? "手动调试" : "运行复盘"} · ${w.run.config_id}`
                            : "准备就绪"}
                      </span>
                      <div className="actions">
                        <button
                          disabled={
                            !w.writable || w.busy || !c || paths.length > 0
                          }
                          onClick={() =>
                            void w.perform(() =>
                              api.runCase(id!, w.caseId, crypto.randomUUID()),
                            )
                          }
                        >
                          <Play size={13} />
                          运行案例
                        </button>
                        <button
                          disabled={!w.writable || w.busy || !paths.length}
                          onClick={() =>
                            void w.perform(() =>
                              api.rerunCase(id!, w.caseId, crypto.randomUUID()),
                            )
                          }
                        >
                          <RefreshCw size={13} />
                          复测
                        </button>
                      </div>
                    </div>
                  </Panel>
                </div>
                <div className="right-column">
                  <Panel name="当前测试任务" icon={<Target />}>
                    <div className="mission">
                      <strong>
                        {w.run
                          ? title(String(w.run.state.config.family)) +
                            " · 导航安全测试"
                          : "等待创建测试任务"}
                      </strong>
                      <code>{id || "NO ACTIVE RUN"}</code>
                      <div className="mission-steps">
                        {["准备", "规划", "审计", "恢复", "报告"].map(
                          (s, i) => (
                            <div
                              key={s}
                              className={
                                (i === 0 && w.run) ||
                                (i === 1 && paths.length) ||
                                (i === 2 && paths.some((p) => p.audit)) ||
                                (i === 3 && paths.length > 1) ||
                                (i === 4 && w.run?.report_available)
                                  ? "done"
                                  : ""
                              }
                            >
                              <span>{i + 1}</span>
                              <small>{s}</small>
                            </div>
                          ),
                        )}
                      </div>
                      <div className="facts">
                        <span>
                          测试员
                          <b>{w.run ? title(w.run.tester || "—") : "—"}</b>
                        </span>
                        <span>
                          剩余动作
                          <b>
                            {w.run?.state.remaining_actions ?? "—"} /{" "}
                            {maxActions}
                          </b>
                        </span>
                        <span>
                          工具调用<b>{w.run?.state.tool_calls ?? 0}</b>
                        </span>
                      </div>
                    </div>
                  </Panel>
                  <Panel
                    name="执行过程"
                    icon={<Bot />}
                    className="trace-panel"
                    action={
                      <span className="cyan">
                        {w.run?.job_active ? "实时更新" : "运行记录"}
                      </span>
                    }
                  >
                    <p className="trace-note">
                      {w.run?.state.runtime_mode === "LIVE_AGNES"
                        ? "Agnes 工具调用记录"
                        : "固定程序执行 · 无模型调用"}
                      <br />
                      以下为系统操作说明
                    </p>
                    {timeline}
                  </Panel>
                </div>
              </div>
              {metrics}
              <div className="bottom-grid">
                {auditPanel}
                <Panel
                  name="导航策略对比"
                  icon={<Route />}
                  action={
                    <button
                      disabled={
                        !w.writable ||
                        w.busy ||
                        !paths.some((p) => p.audit) ||
                        !w.caps?.features.strategy_optimization
                      }
                      onClick={() => void w.optimize()}
                    >
                      <Zap size={14} />
                      比较策略
                    </button>
                  }
                >
                  <p className="panel-description">
                    独立比较路程、转弯和净空；候选结果不会自动替换导航路径。
                  </p>
                  {w.optimization ? (
                    <>
                      <div className="optimization-banner">
                        {title(w.optimization.decision)} ·{" "}
                        {title(w.optimization.selected_profile || "无可用策略")}
                      </div>
                      <div className="table-scroll">
                        <table>
                          <thead>
                            <tr>
                              <th>策略</th>
                              <th>长度 m</th>
                              <th>转弯</th>
                              <th>审计</th>
                            </tr>
                          </thead>
                          <tbody>
                            {w.optimization.candidates.map((x) => (
                              <tr key={x.profile}>
                                <td>{title(x.profile)}</td>
                                <td>{num(x.metrics.path_length_m)}</td>
                                <td>{String(x.metrics.turns ?? "—")}</td>
                                <td>
                                  <span
                                    className={`badge ${x.audit.status === "PASS" ? "green" : "red"}`}
                                  >
                                    {title(x.audit.status)}
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  ) : (
                    <div className="empty">
                      <Route />
                      <strong>用证据比较每一种选择</strong>
                      <p>在手动任务中完成路径审计后，可评估四种导航策略。</p>
                    </div>
                  )}
                </Panel>
              </div>
            </>
          )}
          {page === "scenes" && (
            <>
              <div className="scene-layout">
                <Panel
                  name="场景库"
                  icon={<Box />}
                  action={
                    <span className="badge">
                      {familyCards.length} 类场景 ·{" "}
                      {Object.keys(previews).length} 个几何变体
                    </span>
                  }
                >
                  <div className="scene-filters">
                    {[
                      ["all", "全部场景"],
                      ["fulfillment", "货架仓"],
                      ["sorting", "分拣中心"],
                      ["terminal", "装卸站"],
                      ["warehouse", "仓储"],
                      ["office", "办公"],
                      ["switchback", "折返通道"],
                      ["depot", "密集物流仓"],
                      ["campus", "实验园"],
                      ["labyrinth", "长程回廊"],
                      ["basic", "基础测试"],
                    ].map(([k, v]) => (
                      <button
                        key={k}
                        className={filter === k ? "selected" : ""}
                        onClick={() => {
                          setFilter(k);
                          const target = familyCards.find((x) =>
                            k === "basic"
                              ? [
                                  "dual_route",
                                  "corridor",
                                  "single_entry",
                                ].includes(x.family)
                              : x.family === k,
                          );
                          if (target) selectConfig(target.config_id);
                        }}
                      >
                        {v}
                      </button>
                    ))}
                  </div>
                  <div className="scene-variants">
                    <div>
                      <strong>{title(chosen?.family || "fulfillment")}</strong>
                      <span>同类布局已合并，选择种子切换几何变体</span>
                    </div>
                    <div className="actions">
                      {configOptions
                        .filter((x) => x.family === chosen?.family)
                        .map((x) => (
                          <button
                            key={x.config_id}
                            aria-pressed={x.config_id === configId}
                            className={
                              x.config_id === configId ? "selected" : ""
                            }
                            onClick={() => selectConfig(x.config_id)}
                          >
                            变体 {x.seed}
                          </button>
                        ))}
                    </div>
                  </div>
                  <div className="scene-cards">
                    {familyCards
                      .filter(
                        (x) =>
                          filter === "all" ||
                          (filter === "basic" &&
                            ["dual_route", "corridor", "single_entry"].includes(
                              x.family,
                            )) ||
                          x.family === filter,
                      )
                      .map((x) => {
                        const p = previews[`${x.family}_${x.seed}`];
                        return (
                          <button
                            className={`scene-card ${x.family === chosen?.family ? "selected" : ""}`}
                            aria-label={`选择${title(x.family)}`}
                            key={x.config_id}
                            onClick={() => selectConfig(x.config_id)}
                          >
                            <SceneMap scene={p.scene} task={p.task} compact />
                            <div>
                              <strong>
                                {title(x.family)}{" "}
                                <span>
                                  {[
                                    "fulfillment",
                                    "sorting",
                                    "terminal",
                                  ].includes(x.family)
                                    ? "NEW"
                                    : ""}
                                </span>
                              </strong>
                              <p>
                                {x.description || "固定种子 · 可重复故障测试"}
                              </p>
                              <div className="scene-tags">
                                <span>
                                  {num(p.scene.width * p.scene.resolution_m, 1)}{" "}
                                  ×{" "}
                                  {num(
                                    p.scene.height * p.scene.resolution_m,
                                    1,
                                  )}{" "}
                                  m
                                </span>
                                <span>
                                  {
                                    configOptions.filter(
                                      (v) => v.family === x.family,
                                    ).length
                                  }{" "}
                                  个变体
                                </span>
                              </div>
                            </div>
                            {x.family === chosen?.family && (
                              <span className="chosen-check">
                                <Check size={17} />
                              </span>
                            )}
                          </button>
                        );
                      })}
                  </div>
                </Panel>
                <Panel
                  name="场景预览与配置"
                  icon={<Settings2 />}
                  className="scene-settings"
                >
                  <div className="config-body">{settings}</div>
                </Panel>
              </div>
            </>
          )}
          {page === "maps" && (
            <RouteDetails
              w={w}
              preview={preview}
              onConfigure={() => navigate("scenes")}
            />
          )}
          {page === "strategies" && (
            <StrategyComparison
              w={w}
              preview={preview}
              onConfigure={() => navigate("workspace")}
            />
          )}
          {page === "tasks" && (
            <Panel
              name="测试任务记录"
              icon={<FolderClock />}
              action={
                <button onClick={() => void w.historyPage(w.historyOffset)}>
                  <RefreshCw size={14} />
                  刷新列表
                </button>
              }
            >
              <div className="history-toolbar">
                <label className="search-input">
                  <Search size={16} />
                  <input
                    aria-label="搜索任务"
                    placeholder="搜索本页任务 ID、场景或测试员"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                  />
                </label>
                <select
                  aria-label="筛选本页任务状态"
                  className="history-status"
                  value={historyStatus}
                  onChange={(e) => setHistoryStatus(e.target.value)}
                >
                  <option value="all">全部状态</option>
                  {[
                    "RUNNING",
                    "COMPLETED",
                    "BLOCKED",
                    "CANCELLED",
                    "ERROR",
                  ].map((status) => (
                    <option key={status} value={status}>
                      {title(status)}
                    </option>
                  ))}
                </select>
                <span className="muted">
                  本页显示 {visibleRuns.length} 条 · 共 {w.runTotal} 条
                </span>
              </div>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>任务 / 创建时间</th>
                      <th>场景</th>
                      <th>测试员</th>
                      <th>运行模式</th>
                      <th>状态</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleRuns.map((r) => (
                      <tr key={r.state.run_id}>
                        <td>
                          <code>{r.state.run_id.slice(0, 20)}…</code>
                          <small>
                            {r.created_at
                              ? new Date(r.created_at).toLocaleString("zh-CN")
                              : "历史导入"}
                          </small>
                        </td>
                        <td>{r.config_id || "历史配置"}</td>
                        <td>{title(r.tester || "—")}</td>
                        <td>
                          {r.state.runtime_mode === "LIVE_AGNES"
                            ? "LIVE Agnes"
                            : "确定性"}
                        </td>
                        <td>
                          <span
                            className={`badge ${r.state.status === "COMPLETED" ? "green" : r.state.status === "ERROR" ? "red" : ""}`}
                          >
                            {title(r.state.status)}
                          </span>
                        </td>
                        <td>
                          <button
                            onClick={() => {
                              setPrepared(false);
                              void w.load(r.state.run_id);
                              navigate("workspace");
                            }}
                          >
                            打开 <ArrowRight size={13} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!visibleRuns.length && (
                  <div className="empty">
                    <FolderClock />
                    <p>
                      {w.runs.length
                        ? "本页没有匹配的任务，可调整搜索或状态筛选。"
                        : "还没有运行记录"}
                    </p>
                  </div>
                )}
              </div>
              <div className="pagination">
                <button
                  disabled={w.historyOffset === 0}
                  onClick={() =>
                    void w.historyPage(Math.max(0, w.historyOffset - 30))
                  }
                >
                  上一页
                </button>
                <span>
                  {w.runTotal ? w.historyOffset + 1 : 0}–
                  {Math.min(w.historyOffset + 30, w.runTotal)} / {w.runTotal}
                </span>
                <button
                  disabled={w.historyOffset + 30 >= w.runTotal}
                  onClick={() => void w.historyPage(w.historyOffset + 30)}
                >
                  下一页
                </button>
              </div>
            </Panel>
          )}
          {page === "risk" && (
            <>
              <div className="scope-note">
                <CircleHelp size={15} />
                当前运行的真实审计证据；热区表示违规位置，不代表跨场景事故概率。
              </div>
              <div className="risk-layout">
                <Panel
                  name="路径风险分布"
                  icon={<Radar />}
                  action={
                    <select
                      aria-label="风险案例"
                      value={w.caseId}
                      onChange={(e) => w.select(e.target.value)}
                    >
                      {w.cases.map((x) => (
                        <option
                          key={x.candidate.case_id}
                          value={x.candidate.case_id}
                        >
                          {caseName(x)}
                        </option>
                      ))}
                    </select>
                  }
                >
                  <SceneMap
                    scene={c?.scene_after || preview.scene}
                    task={c?.task || preview.task}
                    before={c?.scene_before}
                    paths={c?.paths}
                    risk
                  />
                  <div className="map-legend">
                    <span>
                      <i className="dot red" />
                      审计违规位置
                    </span>
                    <span>
                      <i className="line green" />
                      恢复路径
                    </span>
                  </div>
                </Panel>
                <div className="risk-side">
                  <Panel name="审计结果分布" icon={<ShieldAlert />}>
                    <div className="donut-wrap">
                      <div
                        className="donut"
                        style={{
                          background: allPaths.length
                            ? `conic-gradient(#00d5b0 0 ${pct(passed, allPaths.length)}%,#ff516d ${pct(passed, allPaths.length)}% ${pct(passed + failed, allPaths.length)}%,#24445f 0)`
                            : "#24445f",
                        }}
                      >
                        <div>
                          <strong>{allPaths.length}</strong>
                          <span>候选路径</span>
                        </div>
                      </div>
                      <div className="donut-labels">
                        <span>
                          <i className="dot green" />
                          通过 <b>{passed}</b>
                        </span>
                        <span>
                          <i className="dot red" />
                          不通过 <b>{failed}</b>
                        </span>
                        <span>
                          <i className="dot" />
                          待审计 / 未定{" "}
                          <b>{allPaths.length - passed - failed}</b>
                        </span>
                      </div>
                    </div>
                  </Panel>
                  <Panel name="场景级测试结果" icon={<Gauge />}>
                    <div className="risk-totals">
                      <div>
                        <strong>{violations.length}</strong>
                        <span>违规记录</span>
                      </div>
                      <div>
                        <strong>{stopped}</strong>
                        <span>安全停止案例</span>
                      </div>
                      <div>
                        <strong>
                          {
                            w.cases.filter((x) =>
                              x.paths.some(
                                (p) =>
                                  p.role === "recovery" &&
                                  p.audit_status === "PASS",
                              ),
                            ).length
                          }
                        </strong>
                        <span>恢复通过案例</span>
                      </div>
                    </div>
                  </Panel>
                </div>
              </div>
              <Panel name="违规证据明细" icon={<TriangleAlert />}>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>案例</th>
                        <th>路径</th>
                        <th>违规类型</th>
                        <th>线段序号</th>
                        <th>剩余净空 m</th>
                        <th>障碍坐标 m</th>
                      </tr>
                    </thead>
                    <tbody>
                      {w.cases.flatMap((x) =>
                        x.paths.flatMap((p) =>
                          (p.audit?.audit.violations || []).map((v, i) => (
                            <tr key={`${p.path_id}-${i}`}>
                              <td>{caseName(x)}</td>
                              <td>
                                {p.role === "original" ? "原始" : "恢复 / 复测"}
                              </td>
                              <td className="red-text">
                                {String(v.code || "—")}
                              </td>
                              <td>{String(v.segment_index ?? "—")}</td>
                              <td>{num(v.remaining_clearance_m, 3)}</td>
                              <td>
                                {Array.isArray(v.obstacle_xy_m)
                                  ? v.obstacle_xy_m
                                      .map((n) => num(n, 3))
                                      .join(", ")
                                  : "—"}
                              </td>
                            </tr>
                          )),
                        ),
                      )}
                    </tbody>
                  </table>
                  {!violations.length && (
                    <p className="empty">
                      暂无违规证据；尚未执行或未审计不等于安全通过。
                    </p>
                  )}
                </div>
              </Panel>
            </>
          )}
          {page === "reports" && (
            <>
              <div className="report-meta">
                <span>
                  <Box size={16} />
                  {w.run?.config_id || "未选择任务"}
                </span>
                <span>
                  <Bot size={16} />
                  {title(w.run?.tester || "—")}
                </span>
                <span>
                  <Clock3 size={16} />
                  {duration(w.elapsed)}
                </span>
                <span>
                  <FileText size={16} />
                  {w.run?.report_available ? "报告已生成" : "等待完成运行"}
                </span>
              </div>
              <div className="report-grid">
                {auditPanel}
                <Panel name="测试摘要" icon={<ClipboardIcon />}>
                  <div className="summary-list">
                    <span>
                      运行编号 <code>{id || "—"}</code>
                    </span>
                    <span>
                      批次结论{" "}
                      <b>{title(w.report?.verdict || "INCONCLUSIVE")}</b>
                    </span>
                    <span>
                      到达目标 <b>{w.report?.reached_count ?? "—"} 个案例</b>
                    </span>
                    <span>
                      安全停止 <b>{w.report?.safe_stop_count ?? "—"} 个案例</b>
                    </span>
                    <span>
                      模型请求 <b>{w.run?.state.model_requests ?? "未测"}</b>
                    </span>
                    <span>
                      模型用量{" "}
                      <b>{w.run?.state.model_tokens ?? "未测"} tokens</b>
                    </span>
                  </div>
                  <p className="scope-note">
                    二维静态几何仿真。审计通过不等于实机安全认证；安全停止不等于到达目标。
                  </p>
                  <button
                    disabled={!w.writable || w.busy}
                    className="primary"
                    onClick={() => void w.perform(() => api.finishRun(id!))}
                  >
                    <CheckCheck size={16} />
                    完成运行并生成报告
                  </button>
                </Panel>
              </div>
              {metrics}
              <div className="report-grid">
                <Panel name="关键事件复盘" icon={<Activity />}>
                  {timeline}
                </Panel>
                <Panel name="路径对比" icon={<Route />}>
                  <select
                    className="report-case"
                    aria-label="报告案例"
                    value={w.caseId}
                    onChange={(e) => w.select(e.target.value)}
                  >
                    {w.cases.map((x) => (
                      <option
                        value={x.candidate.case_id}
                        key={x.candidate.case_id}
                      >
                        {caseName(x)}
                      </option>
                    ))}
                  </select>
                  <SceneMap
                    scene={c?.scene_after || preview.scene}
                    task={c?.task || preview.task}
                    before={c?.scene_before}
                    paths={c?.paths}
                  />
                </Panel>
              </div>
              <Panel name="可下载的报告文件" icon={<FileArchive />}>
                <div className="downloads">
                  {exportLinks}
                  <span className="muted">
                    Markdown 报告 · 原始证据 ZIP · 包含复现材料
                  </span>
                </div>
              </Panel>
            </>
          )}
          <footer>
            <span>
              <ShieldCheck size={13} />
              独立验证 · 证据可追溯
            </span>
            <span>合成场景 / 单机器人 / 固定约束</span>
            <span>
              {w.busy ? "正在执行操作…" : "WORLDGUARD · NAVIGATION ASSURANCE"}
            </span>
          </footer>
        </main>
      </div>
    </div>
  );
}
function ClipboardIcon() {
  return <FileText size={18} />;
}
