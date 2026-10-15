import {
  ArrowRight,
  Check,
  Route,
  ShieldCheck,
  TriangleAlert,
  Zap,
} from "lucide-react";
import { SceneMap } from "./SceneMap";
import { pathSample } from "./mapGeometry";
import { title, eventNames, type useWorkbench } from "./useWorkbench";
import type { components } from "../schema";
type S = components["schemas"];
type Props = {
  w: ReturnType<typeof useWorkbench>;
  preview: { scene: S["SceneView"]; task: S["TaskView"] };
  onConfigure: () => void;
};
const n = (value: number | null | undefined) =>
  value == null ? "—" : value.toFixed(2);
function Cases({ w }: Pick<Props, "w">) {
  return (
    <label className="detail-case-label">
      测试案例
      <select
        aria-label="详情案例"
        value={w.caseId}
        disabled={!w.cases.length}
        onChange={(e) => w.select(e.target.value)}
      >
        {w.cases.length ? (
          w.cases.map((c) => (
            <option key={c.candidate.case_id} value={c.candidate.case_id}>
              {c.candidate.case_id} · {title(c.candidate.fault)}
            </option>
          ))
        ) : (
          <option value="">尚未开始测试</option>
        )}
      </select>
    </label>
  );
}
export function RouteDetails({ w, preview, onConfigure }: Props) {
  const c = w.current,
    latest = c?.paths.at(-1),
    paths = c?.paths || [];
  const events = w.events.filter((e) => !e.case_id || e.case_id === w.caseId);
  return (
    <>
      <div className="detail-toolbar">
        <Cases w={w} />
        <div>
          <span className="muted">当前场景</span>
          <strong>
            {title(
              (c?.scene_after || preview.scene).scene_id
                .split("_")
                .slice(0, -1)
                .join("_"),
            )}
          </strong>
        </div>
        <span className="badge">{c ? "运行证据" : "场景预览"}</span>
        <button onClick={onConfigure}>
          切换测试场景 <ArrowRight size={14} />
        </button>
      </div>
      <div className="route-detail-layout">
        <section className="panel route-map-panel">
          <div className="panel-head">
            <h2>
              <Route size={18} />
              地图、障碍与路径
            </h2>
            <span className="badge">单机器人 · 二维仿真</span>
          </div>
          <SceneMap
            scene={c?.scene_after || preview.scene}
            task={c?.task || preview.task}
            before={c?.scene_before}
            paths={paths}
            playback
          />
        </section>
        <aside className="detail-side">
          <section className="panel">
            <div className="panel-head">
              <h2>
                <ShieldCheck size={18} />
                路径检查结果
              </h2>
            </div>
            <div
              className={`detail-verdict ${latest?.audit_status === "FAIL" || c?.stopped ? "is-warning" : ""}`}
            >
              <ShieldCheck size={25} />
              <div>
                <strong>
                  {c?.stopped
                    ? "安全停止 · 未到达"
                    : latest
                      ? title(latest.audit_status || "NOT_RUN")
                      : "等待执行"}
                </strong>
                <span>
                  {latest
                    ? "独立几何审计 · 当前路径"
                    : "开始测试后显示真实指标"}
                </span>
              </div>
            </div>
            <div className="detail-metrics">
              <div>
                <span>当前路径长度</span>
                <strong>
                  {latest?.plan.path.length
                    ? n(pathSample(latest.plan.path, 0).total)
                    : "—"}{" "}
                  <small>m</small>
                </strong>
              </div>
              <div>
                <span>最小剩余净空</span>
                <strong>
                  {n(latest?.audit?.audit.minimum_remaining_clearance_m)}{" "}
                  <small>m</small>
                </strong>
              </div>
              <div>
                <span>保留路径</span>
                <strong>
                  {paths.length} <small>条</small>
                </strong>
              </div>
              <div>
                <span>违规线段记录</span>
                <strong>{latest?.audit?.audit.violations.length ?? "—"}</strong>
              </div>
            </div>
            <p className="detail-explanation">
              剩余净空已扣除机器人半径与安全余量。回放展示候选路径的位置变化，不表示实机执行。
            </p>
          </section>
          <section className="panel">
            <div className="panel-head">
              <h2>原始与恢复路径</h2>
            </div>
            <div className="path-records">
              {paths.length ? (
                paths.map((p, i) => (
                  <div key={p.path_id}>
                    <span className={`path-index ${p.role}`}>
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <div>
                      <strong>
                        {p.role === "original"
                          ? "原始规划"
                          : p.role === "recovery"
                            ? "恢复规划"
                            : "复测规划"}
                      </strong>
                      <small>
                        {p.plan.path.length
                          ? `${n(pathSample(p.plan.path, 0).total)} m`
                          : "无可行路径"}{" "}
                        · {p.plan.path.length} 个路径点
                      </small>
                    </div>
                    <span
                      className={`badge ${p.audit_status === "PASS" ? "green" : p.audit_status === "FAIL" ? "red" : ""}`}
                    >
                      {title(p.audit_status || "NOT_RUN")}
                    </span>
                  </div>
                ))
              ) : (
                <p className="detail-explanation">暂无路径证据</p>
              )}
            </div>
          </section>
          <section className="panel">
            <div className="panel-head">
              <h2>关键操作记录</h2>
              <span className="badge">{events.length}</span>
            </div>
            <div className="detail-events">
              {events
                .slice(-8)
                .reverse()
                .map((e) => (
                  <div key={e.event_id}>
                    <time>
                      {new Date(e.timestamp).toLocaleTimeString("zh-CN", {
                        hour12: false,
                      })}
                    </time>
                    <i />
                    <div>
                      <strong>
                        {eventNames[e.tool_name]?.[0] || e.tool_name}
                      </strong>
                      <small>{e.case_id || "运行级操作"}</small>
                    </div>
                  </div>
                ))}
              {!events.length && (
                <p className="detail-explanation">暂无操作记录</p>
              )}
            </div>
          </section>
        </aside>
      </div>
    </>
  );
}
export function StrategyComparison({ w, preview, onConfigure }: Props) {
  const result = w.optimization,
    c = w.current;
  const profiles = {
    baseline: "以路径长度作为基准",
    fewer_turns: "优先减少转弯次数",
    balanced: "综合路径长度、转弯与净空",
    clearance: "优先选择更宽裕的通行空间",
  };
  return (
    <>
      <div className="detail-toolbar">
        <Cases w={w} />
        <div>
          <span className="muted">对比结果</span>
          <strong>{result ? title(result.decision) : "尚未评估"}</strong>
        </div>
        <span className="badge">确定性算法 · 0 次模型调用</span>
        <button
          className="primary"
          disabled={
            !w.writable ||
            w.busy ||
            !c?.paths.some((p) => p.audit) ||
            !w.caps?.features.strategy_optimization
          }
          onClick={() => void w.optimize()}
        >
          <Zap size={15} />
          评估四种策略
        </button>
      </div>
      {result ? (
        <>
          <div className="strategy-intro">
            <div>
              <span className="eyebrow">CANDIDATE COMPARISON</span>
              <h2>同一地图、同一约束，比较四条路线</h2>
              <p>
                每个候选均经过独立审计；选中的方案作为比较结果保存，不自动替换当前导航路径。
              </p>
            </div>
            <span className="badge green">
              推荐：{title(result.selected_profile || "暂无安全候选")}
            </span>
          </div>
          <div className="strategy-cards">
            {result.candidates.map((x, i) => (
              <section
                key={x.profile}
                className={`panel strategy-card ${x.profile === result.selected_profile ? "recommended" : ""}`}
              >
                <div className="strategy-card-head">
                  <span>{String(i + 1).padStart(2, "0")}</span>
                  <strong>{title(x.profile)}</strong>
                  {x.profile === result.selected_profile && (
                    <span className="badge green">
                      <Check size={12} />
                      推荐
                    </span>
                  )}
                </div>
                <p>{profiles[x.profile]}</p>
                <SceneMap
                  scene={c?.scene_after || preview.scene}
                  task={c?.task || preview.task}
                  before={c?.scene_before}
                  compact
                  pathColor={
                    {
                      baseline: "#ffb747",
                      fewer_turns: "#23e9c0",
                      balanced: "#29d9f5",
                      clearance: "#bc98ff",
                    }[x.profile]
                  }
                  paths={[
                    {
                      case_id: result.case_id,
                      path_id: x.profile,
                      role: "recovery",
                      plan: x.plan,
                      audit_status: x.audit.status,
                      audit: {
                        case_id: result.case_id,
                        path_id: x.profile,
                        evidence_id: "",
                        audit: x.audit,
                      },
                    },
                  ]}
                />
                <dl>
                  <div>
                    <dt>路径长度</dt>
                    <dd>
                      {n(x.metrics.path_length_m)} <small>m</small>
                    </dd>
                  </div>
                  <div>
                    <dt>转弯次数</dt>
                    <dd>
                      {x.metrics.turns ?? "—"} <small>次</small>
                    </dd>
                  </div>
                  <div>
                    <dt>最小剩余净空</dt>
                    <dd>
                      {n(x.metrics.minimum_remaining_clearance_m)}{" "}
                      <small>m</small>
                    </dd>
                  </div>
                  <div>
                    <dt>加权代价 · 越低越好</dt>
                    <dd>{n(x.score)}</dd>
                  </div>
                  <div>
                    <dt>独立审计</dt>
                    <dd
                      className={
                        x.audit.status === "PASS" ? "success-text" : "danger"
                      }
                    >
                      {title(x.audit.status)}
                    </dd>
                  </div>
                </dl>
              </section>
            ))}
          </div>
          <div className="strategy-bottom">
            <section className="panel">
              <div className="panel-head">
                <h2>路径长度对比</h2>
                <span className="muted">m · 越短越好</span>
              </div>
              <div className="comparison-bars">
                {result.candidates.map((x) => (
                  <div key={x.profile}>
                    <span>{title(x.profile)}</span>
                    <div>
                      <i
                        style={{
                          width: `${((x.metrics.path_length_m || 0) / Math.max(1, ...result.candidates.map((v) => v.metrics.path_length_m || 0))) * 100}%`,
                        }}
                      />
                    </div>
                    <b>{n(x.metrics.path_length_m)}</b>
                  </div>
                ))}
              </div>
            </section>
            <section className="panel">
              <div className="panel-head">
                <h2>
                  <ShieldCheck size={17} />
                  评估依据
                </h2>
              </div>
              <div className="strategy-evidence">
                <p>
                  所有候选共享原始地图、起终点和机器人约束，审计未通过的方案不可选。
                </p>
                <p>
                  相对基准：路径长度变化{" "}
                  <b>{n(result.metric_changes?.path_length_m)} m</b>，转弯变化{" "}
                  <b>{result.metric_changes?.turns ?? "—"} 次</b>。
                </p>
                <details>
                  <summary>查看原始选择依据与证据标识</summary>
                  <p>{result.selection_reason || "未提供额外说明"}</p>
                  <code>
                    scene: {result.scene_hash}
                    <br />
                    constraints: {result.constraints_hash}
                  </code>
                </details>
              </div>
            </section>
          </div>
        </>
      ) : (
        <div className="panel strategy-empty">
          <Route size={42} />
          <h2>让每一次优化都有比较依据</h2>
          <p>
            在手动任务中执行案例并完成独立审计，再评估四种策略。历史任务可查看已经保存的评估结果。
          </p>
          <div className="strategy-placeholder-labels">
            {Object.entries(profiles).map(([key, value]) => (
              <div key={key}>
                <ShieldCheck size={22} />
                <strong>{title(key)}</strong>
                <span>{value}</span>
              </div>
            ))}
          </div>
          <button onClick={onConfigure}>
            进入工作台 <ArrowRight size={15} />
          </button>
          <small>
            <TriangleAlert size={13} /> 当前没有评估数据，不展示示例分数
          </small>
        </div>
      )}
    </>
  );
}
