"""Streamlit client of the same HTTP API used by the collaborator frontend."""

import os
import uuid

import streamlit as st

from worldguard.visuals import scene_svg
from worldguard.workbench_client import WorkbenchClient, WorkbenchError

API = os.environ.get("WORLDGUARD_API_URL", "http://127.0.0.1:8520").rstrip("/")
client = WorkbenchClient(API)
st.set_page_config(page_title="WorldGuard", page_icon="◈", layout="wide")
st.title("WorldGuard")
st.caption("部署前导航故障测试 · 单机器人二维几何仿真 · 不构成实机安全认证")

try:
    capabilities = client.request("/capabilities")
    runs = client.request("/runs?limit=100")["items"]
    connected = True
except WorkbenchError:
    capabilities, runs, connected = {}, [], False

live_ready = capabilities.get("features", {}).get("live_agnes", False)
active_ids = {r["state"]["run_id"] for r in runs if r["job_active"]}
if not connected:
    st.error("后端未连接。请使用 scripts/launch.py 启动工作台与 API，或先启动 python -m worldguard.api。")
elif live_ready:
    st.success("Agnes 已接入 · 点击「开始 LIVE Agnes 测试」可调用真实模型；离线测试仍使用固定规则。")
else:
    st.info("离线模式可用。后端尚未启用 LIVE；请按 docs/AGH_LIVE.md 配置本机授权并重启 API。")


def start_run(mode, config_id, tester):
    # Keep the same request after a lost response; refresh never submits it.
    pending = st.session_state.get("pending_create")
    fields = {"config_id": config_id, "runtime_mode": mode,
              "execution_mode": "automatic", "tester": tester}
    if pending and any(pending[k] != value for k, value in fields.items()):
        st.error("上次提交结果未知，请保留原配置重试，以免重复创建运行。")
        return
    payload = pending or {**fields, "request_id": "ui_" + uuid.uuid4().hex}
    st.session_state["pending_create"] = payload
    try:
        result = client.request("/runs", payload)
    except WorkbenchError as error:
        st.error(f"提交未确认：{error}。保持配置再次点击将重试同一请求；不会自动改为离线。")
        return
    st.session_state.pop("pending_create", None)
    st.session_state["view_run"] = result["state"]["run_id"]
    st.rerun()


with st.sidebar:
    st.header("测试配置")
    family = st.selectbox("场景", ["dual_route", "corridor", "single_entry"],
                          format_func=lambda value: {"dual_route": "双通道绕行", "corridor": "净空走廊",
                                                     "single_entry": "单入口目标区"}[value])
    st.selectbox("导航器", ["reference_safe_astar"])
    view = st.selectbox("规划地图视图", ["stale", "current"],
                        format_func=lambda value: "陈旧视图（显式故障测试）" if value == "stale" else "当前地图")
    method = st.selectbox("离线测试员", ["FixedCoverage", "SeededRandom", "AdaptiveRule"])
    st.caption("LIVE 由 Agnes 选择工具和恢复动作；上面的测试员仅用于离线模式。")
    st.caption("固定约束：半径 0.18 m + 余量 0.05 m；最多 12 次导航执行。模型请求受后端已授权额度限制。")
    if st.button("开始 LIVE Agnes 测试", type="primary",
                 disabled=not connected or not live_ready or bool(active_ids), width="stretch"):
        start_run("LIVE_AGNES", family + "_" + view, "AgnesAGH")
    if st.button("开始离线测试", disabled=not connected or bool(active_ids), width="stretch"):
        start_run("DETERMINISTIC", family + "_" + view, method)
    st.link_button("后端接口文档", API + "/docs")
    if st.button("刷新连接与记录"):
        st.rerun()


@st.cache_data(ttl=60, show_spinner=False)
def download(base_url, path):
    return WorkbenchClient(base_url).request(path, raw=True)


@st.fragment(run_every=2)
def monitor():
    try:
        records = client.request("/runs?limit=100")["items"]
        current_active = {r["state"]["run_id"] for r in records if r["job_active"]}
        if current_active != active_ids:
            st.rerun()
        if not records:
            st.subheader("从左侧开始一次测试")
            return
        names = [r["state"]["run_id"] for r in records]
        selected = st.session_state.get("view_run")
        if selected and selected not in names:
            records.append(client.request("/runs/" + selected))
            names.append(selected)
        labels = {r["state"]["run_id"]: f"{r['state']['runtime_mode']} · {r['state']['status']} · "
                  f"{r['state']['run_id']}" for r in records}
        rid = st.selectbox("查看运行记录", names, key="view_run", format_func=lambda value: labels[value])
        base = "/runs/" + rid
        run = client.request(base)
        state = run["state"]
        st.subheader(f"{state['runtime_mode']} · {state['status']}")
        if run["job_active"]:
            st.info("Agnes 正在调用工具，等待模型响应时也会持续刷新。" if state["runtime_mode"] == "LIVE_AGNES"
                    else "正在运行离线导航与独立检查……")
            if st.button("取消运行", disabled=state["status"] == "CANCELLED"):
                client.request(base + "/stop", {"reason": "USER_CANCELLED"})
                st.rerun()
        if run["interrupted"]:
            st.warning("服务重启前的运行未完成，当前为只读记录。")
        if state["status"] in {"ERROR", "BLOCKED"}:
            st.error("本次执行未完整完成，请查看事件和会话证据。模型、额度或服务错误不计为导航缺陷。")
            code = (run.get("execution_error") or {}).get("code")
            reasons = {"MODEL_REQUEST_BUDGET": "本机设置的本次或累计请求额度已耗尽。",
                       "MODEL_REQUEST_TIMEOUT": "模型请求等待超时，已有结果已保存，可稍后重新测试。",
                       "MODEL_RATE_LIMIT": "模型服务限流，有限重试后仍未完成，请稍后重试。",
                       "MODEL_QUOTA_EXHAUSTED": "模型服务额度不足，请检查服务端账户额度。",
                       "MODEL_AUTH_ERROR": "模型服务认证失败，请检查本机 AGH 配置。",
                       "MODEL_TRANSPORT_ERROR": "模型连接失败，已有结果已保存。",
                       "WALL_TIME_EXHAUSTED": "本次运行达到总时间上限，已有结果已保存。",
                       "MODEL_BUDGET_BUSY": "模型用量记录正在被另一任务更新，请稍后再试。",
                       "AGH_FLOW_INCOMPLETE": "模型会话未完成收尾，已保留执行结果。",
                       "AGH_CAMPAIGN_NOT_COMPLETE": "部分案例尚未执行或验证，已保留已有结果。"}
            if code:
                st.caption(reasons.get(code, "执行服务发生错误。") + " 错误码：" + code)
        if state["status"] == "CANCELLED":
            st.warning("已取消。正在结束调用并保存已有证据。" if run["job_active"] else "已取消，已有结果保留。")
        a, b, c = st.columns(3)
        a.metric("导航执行", state["sut_executions"])
        b.metric("业务工具调用", state["tool_calls"])
        count = state["model_requests"]
        c.metric("模型请求尝试", "结算中" if run["job_active"] and state["runtime_mode"] == "LIVE_AGNES"
                 else count if count is not None else "未知")
        st.caption(f"run_id: {rid} · {run.get('tester') or '历史记录'} · "
                   "模型编排与独立几何检查分别记录；SAFE_STOP 不等于到达。")
        events = client.request(base + "/events?limit=500")["items"]
        if events:
            st.caption("最近动作：" + events[-1]["tool_name"])
        with st.expander("业务工具事件", expanded=run["job_active"]):
            st.dataframe(events, width="stretch")
        candidates = client.request(base + "/candidates")["items"]
        if candidates:
            cid = st.selectbox("案例", [c["case_id"] for c in candidates], key="case_" + rid)
            case_path = base + "/cases/" + cid
            case = client.request(case_path)
            left, right = st.columns([3, 2])
            with left:
                st.image(client.request(case_path + "/map.svg", raw=True).decode("utf-8"), width="stretch")
                st.caption("红块：注入障碍 · 橙虚线：原路径 · 青实线：恢复路径 · 紫线：违规段 · S/G：起终点")
            with right:
                original = next((p for p in case["paths"] if p["role"] == "original"), None)
                recovery = next((p for p in reversed(case["paths"]) if p["role"] == "recovery"), None)
                st.write(f"原始审计：**{original['audit_status'] if original else 'NOT_RUN'}**")
                st.write(f"恢复审计：**{recovery['audit_status'] if recovery else 'NOT_RUN'}**")
                result = case.get("result")
                st.write(f"导航结果：**{result['navigation_status'] if result else '等待报告封存'}**")
                if case["stopped"]:
                    st.write("本案例已执行安全停止。")
                with st.expander("路径与检查证据"):
                    st.json(case["paths"])
            if capabilities.get("features", {}).get("strategy_optimization") and not run["job_active"]:
                st.subheader("导航策略优化")
                st.caption("同一当前地图与任务，比较 A* 基线、减少转弯、净空优先和均衡策略。独立验收后选择；不修改原始报告。")
                if st.button("优化并对比当前案例", key="optimize_" + rid + cid):
                    with st.spinner("正在规划四个候选并独立验收……"):
                        client.request(case_path + "/optimize", {})
                try:
                    optimization = client.request(case_path + "/optimization")
                except WorkbenchError as error:
                    if str(error) != "OPTIMIZATION_NOT_READY":
                        raise
                    optimization = None
                if optimization:
                    decisions = {"IMPROVED": "找到更优方案", "NO_IMPROVEMENT": "本次没有更优方案，保留基线",
                                 "NO_SAFE_PATH": "本次候选没有安全路径"}
                    st.write(decisions[optimization["decision"]])
                    st.dataframe([{"策略": c["profile"], "独立审计": c["audit"]["status"],
                                   **c["metrics"], "代价（越低越好）": c["score"]}
                                  for c in optimization["candidates"]], width="stretch")
                    selected = next((c for c in optimization["candidates"]
                                     if c["profile"] == optimization["selected_profile"]), None)
                    if selected:
                        baseline = optimization["candidates"][0]
                        st.image(scene_svg(optimization["scene"], optimization["scene"], optimization["task"],
                                           baseline["plan"], selected["plan"], baseline["audit"]), width="stretch")
                        st.caption("橙虚线：当前地图上的基线；青实线：选中策略。评分仅适用于本案例；未验证跨地图收益。")
        if run["report_available"]:
            report = client.request(base + "/report")
            st.subheader(f"报告：{report['verdict']}")
            a, b, c = st.columns(3)
            a.metric("已执行案例", f"{report['executed_cases']} / {report['planned_cases']}")
            b.metric("到达 REACHED", report["reached_count"])
            c.metric("安全停止 SAFE_STOP", report["safe_stop_count"])
            if not run["job_active"]:
                st.download_button("导出完整证据 ZIP", download(API, base + "/export"),
                                   file_name=rid + ".zip", mime="application/zip")
                st.download_button("下载 Markdown 报告", download(API, base + "/report.md"),
                                   file_name=rid + ".md", mime="text/markdown")
        else:
            st.caption("报告将在调用结束、会话证据核验后生成。")
        if run.get("agh_session"):
            with st.expander("Agnes 会话与真实调用证据"):
                st.json(run["agh_session"])
    except WorkbenchError as error:
        st.error(f"后端读取失败：{error}。恢复连接后会继续读取，不会重复发起测试。")


if connected:
    monitor()
