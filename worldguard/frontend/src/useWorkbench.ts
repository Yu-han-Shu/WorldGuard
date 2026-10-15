import { useCallback, useEffect, useRef, useState } from "react";
import {
  createWorldGuardClient,
  WorldGuardError,
  type Run,
  type Case,
  type Report,
  type Optimization,
} from "../client";
import type { components } from "../schema";
type S = components["schemas"];
export const api = createWorldGuardClient(
  import.meta.env.VITE_WORLDGUARD_API_URL || "http://127.0.0.1:8520",
);
export const names: Record<string, string> = {
  challenge: "错位通道仓",
  generated: "程序化仓库",
  fulfillment: "立体货架仓",
  sorting: "交错分拣中心",
  terminal: "联运装卸站",
  depot: "密集物流仓",
  campus: "多区实验园",
  labyrinth: "长程回廊",
  warehouse: "仓储物流",
  office: "多室办公",
  switchback: "折返通道",
  dual_route: "双通道",
  corridor: "狭窄走廊",
  single_entry: "单入口目标区",
  FixedCoverage: "固定覆盖",
  SeededRandom: "种子随机",
  AdaptiveRule: "自适应规则",
  AgnesAGH: "Agnes 智能测试员",
  RUNNING: "运行中",
  COMPLETED: "已完成",
  CANCELLED: "已取消",
  BLOCKED: "已阻断",
  ERROR: "异常",
  PASS: "通过",
  FAIL: "不通过",
  UNKNOWN: "未定",
  NOT_RUN: "待审计",
  PLANNED: "规划成功",
  NO_PATH: "无路径",
  NONE: "正常基准",
  BLOCK_ROUTE: "道路阻断",
  DISCONNECT_GOAL: "目标隔断",
  PINCH_CLEARANCE: "通道收窄",
  BOUNDED_PASS: "限定范围通过",
  FAILURES_FOUND: "发现原始失败",
  INCONCLUSIVE: "证据不足",
  REFRESH_MAP_REPLAN: "更新地图并重新规划",
  SAFE_STOP: "安全停止",
  IMPROVED: "发现更优候选",
  NO_IMPROVEMENT: "未发现改善",
  NO_SAFE_PATH: "没有安全候选",
  baseline: "基准策略",
  fewer_turns: "减少转弯",
  clearance: "优先净空",
  balanced: "综合平衡",
};
export const title = (s: string) => names[s] || s;
export const eventNames: Record<string, [string, string]> = {
  mission_plan_confirmed: ["确认目标计划", "固定案例范围、地图与预算"],
  wg_publish_decision: [
    "发布公开行动摘要",
    "简短说明计划或依据证据采取的下一步",
  ],
  live_execution_started: ["启动 Agnes 执行环境", "通过官方 AGH 调用受控工具"],
  wg_create_campaign: ["创建测试任务", "冻结地图、目标与预算"],
  wg_list_candidates: ["读取故障案例", "获取本场景允许注入的故障"],
  wg_run_case: ["执行导航规划", "使用配置的地图计算候选路线"],
  wg_audit_path: ["独立检查路径", "按照真实障碍与机器人足迹检查整条路径"],
  wg_recover_case: ["执行恢复决策", "依据审计证据重规划或停止"],
  wg_rerun_case: ["复测相同案例", "使用相同条件检查可重复性"],
  wg_optimize_case: ["比较导航策略", "比较长度、转弯和安全间距"],
  wg_finish_campaign: ["生成测试报告", "汇总结果并保存原始失败证据"],
  wg_stop_campaign: ["取消测试任务", "停止后续操作，保留已有证据"],
};
export function useWorkbench() {
  const [configs, setConfigs] = useState<S["ConfigView"][]>([]),
    [caps, setCaps] = useState<S["CapabilitiesView"] | null>(null);
  const [run, setRun] = useState<Run | null>(null),
    [cases, setCases] = useState<Case[]>([]),
    [events, setEvents] = useState<S["EventView"][]>([]),
    [report, setReport] = useState<Report | null>(null),
    [optimization, setOptimization] = useState<Optimization | null>(null);
  const [caseId, setCaseId] = useState(""),
    [runs, setRuns] = useState<Run[]>([]),
    [runTotal, setRunTotal] = useState(0),
    [historyOffset, setHistoryOffset] = useState(0),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [connected, setConnected] = useState(false),
    [loading, setLoading] = useState(true);
  const active = useRef(""),
    selection = useRef(""),
    epoch = useRef(0),
    refreshing = useRef(false);
  const fail = (e: unknown) =>
    setError(
      e instanceof WorldGuardError
        ? `${e.code} · ${e.message}`
        : e instanceof Error
          ? e.message
          : String(e),
    );
  const historyPage = useCallback(async (offset = 0) => {
    const p = await api.listRuns(offset, 30);
    setRuns(p.items);
    setRunTotal(p.total);
    setHistoryOffset(offset);
  }, []);
  const refresh = useCallback(async (id = active.current) => {
    if (!id) return;
    const generation = epoch.current;
    const r = await api.getRun(id);
    const c = await api.candidates(id);
    const [details, first, rep] = await Promise.all([
      Promise.all(c.items.map((x) => api.getCase(id, x.case_id))),
      api.events(id),
      r.report_available ? api.report(id) : Promise.resolve(null),
    ]);
    const all = [...first.items];
    let p = first;
    while (p.has_more) {
      p = await api.events(id, p.next_cursor);
      all.push(...p.items);
    }
    if (generation !== epoch.current || active.current !== id) return;
    const chosen = details.some(
      (x) => x.candidate.case_id === selection.current,
    )
      ? selection.current
      : details[0]?.candidate.case_id || "";
    selection.current = chosen;
    setCaseId(chosen);
    setRun(r);
    setRuns((items) =>
      items.map((item) => (item.state.run_id === id ? r : item)),
    );
    setCases(details);
    setEvents(all);
    setReport(rep);
    setConnected(true);
    history.replaceState(
      null,
      "",
      `?run=${encodeURIComponent(id)}&case=${encodeURIComponent(chosen)}${location.hash}`,
    );
  }, []);
  const load = useCallback(
    async (id: string, selected = "") => {
      epoch.current++;
      active.current = id;
      selection.current = selected;
      setCaseId("");
      setCases([]);
      setEvents([]);
      setReport(null);
      setOptimization(null);
      setRun(null);
      setError("");
      setLoading(true);
      try {
        await refresh(id);
      } catch (e) {
        fail(e);
      } finally {
        setLoading(false);
      }
    },
    [refresh],
  );
  useEffect(() => {
    let cancelled = false;
    void Promise.all([api.configs(), api.capabilities(), api.listRuns(0, 30)])
      .then(async ([c, cap, h]) => {
        if (cancelled) return;
        setConfigs(c.items);
        setCaps(cap);
        setRuns(h.items);
        setRunTotal(h.total);
        setConnected(true);
        const q = new URLSearchParams(location.search);
        const id = q.get("run");
        if (id) await load(id, q.get("case") || "");
      })
      .catch((e) => {
        if (!cancelled) {
          fail(e);
          setConnected(false);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [load]);
  useEffect(() => {
    if (!run || run.state.status !== "RUNNING") return;
    const timer = setInterval(() => {
      if (refreshing.current) return;
      refreshing.current = true;
      void refresh()
        .catch((e) => {
          fail(e);
          setConnected(false);
        })
        .finally(() => {
          refreshing.current = false;
        });
    }, 1800);
    return () => clearInterval(timer);
  }, [run?.state.run_id, run?.state.status, refresh]);
  useEffect(() => {
    let disposed = false;
    setOptimization(null);
    if (run && caseId)
      void api
        .optimization(run.state.run_id, caseId)
        .then((o) => {
          if (!disposed) setOptimization(o);
        })
        .catch(() => {});
    return () => {
      disposed = true;
    };
  }, [run?.state.run_id, caseId]);
  function select(id: string) {
    selection.current = id;
    setCaseId(id);
    if (active.current)
      history.replaceState(
        null,
        "",
        `?run=${active.current}&case=${encodeURIComponent(id)}${location.hash}`,
      );
  }
  async function perform(fn: () => Promise<unknown>) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await fn();
      await refresh();
      await historyPage();
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }
  async function create(body: Omit<S["CreateRun"], "request_id">) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const r = await api.createRun({
        ...body,
        request_id: crypto.randomUUID(),
      });
      await load(r.state.run_id);
      await historyPage();
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }
  const current = cases.find((c) => c.candidate.case_id === caseId) || null;
  const writable =
    !!run &&
    !run.read_only &&
    !run.job_active &&
    run.state.status === "RUNNING";
  const cancellable = !!run && !run.read_only && run.state.status === "RUNNING";
  // Final event timestamps remain stable even with legacy backends whose elapsed counter keeps growing.
  const terminal = events.findLast((e) => e.status !== "RUNNING");
  const elapsed =
    run?.state.status === "RUNNING"
      ? run.state.elapsed_seconds
      : terminal && events[0]
        ? Math.max(
            0,
            (Date.parse(terminal.timestamp) - Date.parse(events[0].timestamp)) /
              1000,
          )
        : null;
  return {
    configs:
      !run?.config_id || configs.some((c) => c.config_id === run.config_id)
        ? configs
        : [
            ...configs,
            {
              ...run.state.config,
              config_id: run.config_id,
              description: "程序化生成场景 · 已冻结运行快照",
              width_cells: current?.scene_before.width || 0,
              height_cells: current?.scene_before.height || 0,
            } as S["ConfigView"],
          ],
    caps,
    run,
    cases,
    caseId,
    current,
    events,
    report,
    optimization,
    runs,
    runTotal,
    historyOffset,
    busy,
    error,
    connected,
    loading,
    writable,
    cancellable,
    elapsed,
    select,
    create,
    perform,
    load,
    clear: () => {
      epoch.current++;
      active.current = "";
      selection.current = "";
      setRun(null);
      setCases([]);
      setCaseId("");
      setEvents([]);
      setReport(null);
      setOptimization(null);
      setError("");
      setLoading(false);
    },
    refresh: () => perform(() => refresh()),
    historyPage: (o = 0) => historyPage(o).catch(fail),
    dismiss: () => setError(""),
    optimize: () =>
      perform(async () => {
        if (run && caseId)
          setOptimization(await api.optimizeCase(run.state.run_id, caseId));
      }),
  };
}
