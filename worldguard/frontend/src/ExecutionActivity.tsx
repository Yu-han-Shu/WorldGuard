import { useEffect, useState } from "react";
import { Activity, ArrowRight, Check, ChevronDown, Clock3, FileText, LoaderCircle, TriangleAlert } from "lucide-react";
import type { Run } from "../client";
import type { components } from "../schema";
import type { PublicDecision } from "./missionTypes";
import { eventNames, title } from "./useWorkbench";
import { elapsedLabel, executionActivity } from "./executionStatus";

type Event = components["schemas"]["EventView"];
const caseName = (id: string) => id === "normal" ? "正常通行基准" : `${title(id.replace(/_\d+$/, "").toUpperCase())} ${id.split("_").at(-1)}`;
const clock = (stamp: string) => new Date(stamp).toLocaleTimeString("zh-CN", { hour12: false });

export function ExecutionActivity({ run, events, decisions, connected, onInspect }: {
  run: Run;
  events: Event[];
  decisions: PublicDecision[];
  connected: boolean;
  onInspect: (event: Event) => void;
}) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const activity = executionActivity({ events, decisions, createdAt: run.created_at, now, connected, jobActive: run.job_active, manual: run.execution_mode === "manual", interrupted: run.interrupted });
  const recent = events.slice(-3).reverse();
  const latest = events.at(-1);
  const decision = decisions.at(-1);
  const live = run.state.runtime_mode === "LIVE_AGNES";
  const working = connected && run.job_active && !run.interrupted;
  const row = (event: Event) => {
    const problem = /ERROR|FAIL|BLOCKED/i.test(event.status);
    return <li key={event.event_id}>
      <button onClick={() => onInspect(event)}>
        <span className={problem ? "activity-event-icon warning" : "activity-event-icon"}>{problem ? <TriangleAlert size={14} /> : <Check size={14} />}</span>
        <span><b>{eventNames[event.tool_name]?.[0] || event.tool_name}</b><small>{event.case_id ? caseName(event.case_id) : eventNames[event.tool_name]?.[1] || "任务记录"}{problem ? ` · ${event.status}` : ""}</small></span>
        <time dateTime={event.timestamp}>{clock(event.timestamp)}</time><ArrowRight size={13} />
      </button>
    </li>;
  };
  return <section className={"studio-live-execution " + (working ? "is-connected" : "is-disconnected")} aria-labelledby="live-execution-title">
    <header>
      <span className="activity-heading-icon"><Activity size={20} /></span>
      <div><h2 id="live-execution-title">执行过程</h2><p>{live ? "评测 Agent" : "自动测试 · 固定规则"}<span>{working ? "运行中" : run.interrupted ? "已中断" : "等待中"}</span></p></div>
      <div className="activity-counts"><span><Clock3 size={13} />用时 {elapsedLabel(run.state.elapsed_seconds)}</span><span>{run.state.tool_calls} 次工具调用</span><span>{events.length} 条记录</span></div>
    </header>
    <div className="activity-body">
      <div className="activity-current">
        <div className="activity-status" role="status"><span className="activity-orbit">{working ? <LoaderCircle size={19} /> : <Clock3 size={19} />}</span><h3>{activity.title}</h3></div>
        <p>{activity.description}</p>
        <div className="activity-latest">{latest ? <>最近记录：{eventNames[latest.tool_name]?.[0] || latest.tool_name}</> : "尚未收到工具返回"}</div>
        {activity.idleSeconds !== null && <small className="activity-age">{events.length || decisions.length ? "距最近记录" : "已等待"} {elapsedLabel(activity.idleSeconds)}</small>}
        {decision && <blockquote key={decision.timestamp}><b>最近公开决策 · {clock(decision.timestamp)}</b><p>{decision.summary}</p></blockquote>}
      </div>
      <div className="activity-timeline">
        <div className="activity-timeline-title"><b>最近执行记录</b><span>新记录在上方</span></div>
        {recent.length ? <ol>{recent.map(row)}</ol> : <div className="activity-empty"><FileText size={22} /><p>工具返回后显示动作、案例和时间。<br />原始结果与后续恢复会分别保留。</p></div>}
        {events.length > 3 && <details className="activity-older"><summary>查看更早的 {events.length - 3} 条记录<ChevronDown size={13} /></summary><ol>{events.slice(0, -3).reverse().map(row)}</ol></details>}
      </div>
    </div>
  </section>;
}
