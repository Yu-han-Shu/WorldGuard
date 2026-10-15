# Agnes 最小执行链路

2026-10-13，Windows / PowerShell。官方 AGH 固定提交 `dc267c3c78429933e2b3d8c5d544e56bb980a574`。
用户授权“请求也无所谓”“反正是免费模型”“全部走一遍”，随后明确取消调试用累计请求限制，并要求修复调用中断。本机预算文件设 `max_total_requests=null`；每运行最多 30 次、最大输出 2000 tokens。2026-10-13 RUNTIME_FIX 将单请求等待设为 90 秒、LIVE 总时限统一为 300 秒。历史请求分配记录继续保留，费用 null；不购买或升级服务。

## 实际执行方式

HTTP 创建 LIVE 运行 → 共用 CampaignRunner → 临时认证 loopback MCP → 官方 AGH Host → 官方模型适配器 → Agnes → MCP 工具 → 原始地图上的独立审计 → 恢复/停止 → 报告与 ZIP。

`scripts/agh_host.mjs` 使用生产 `createHost`、真实内置 seams/package loader、官方 wire adapter 和 MCP connector。没有测试 Host、模拟 provider、第二套自建 LLM 工具循环，也没有修改上游代码。
Agnes 模型从官方配置服务的本机已配置目录解析，端点必须为 `https://api.agnes-ai.cn`，模型固定为已配置的 `agnes-3.0-flash`。真实 API Key 不经前端或项目日志。

每运行创建独立 AGH home 和空工作目录；官方密钥解析器只读使用已配置凭据引用。不会修改日常 AGH 的模型设置、会话或 daemon。
通过官方 Host row 生命周期移除编码、文件、shell、搜索、子 Agent 与 Computer Use 工具。实际披露仅 10 个本项目 MCP 工具；模型请求边界再次检查工具名单。

MCP 仅监听随机本机端口，每运行随机 bearer，绑定唯一 run_id。模型不能改变端点、令牌、运行目录或访问其他运行。
几何/SUT 仍为确定性实现，LIVE_AGNES 表示编排来自真实模型，不表示规划和验收改用模型。

## 请求限制

`boundedProvider` 包住官方 Provider 的每次 `infer`，主模型、标题生成等辅助请求都计入同一额度。发出前预留额度、验证 route/model、输出上限和工具名单，关闭 wire adapter 内部重试。单请求由 `request_timeout_seconds` 配置（兼容默认 min(90, 总时限)），不得超过运行剩余时间。
官方 AGH 负责可重试错误的至多一次重试；每次真实尝试都计入原 30 次上限，不另建工具调用循环。429 按服务端 Retry-After 等待；等待超过总时限则停止。取消、认证失败和额度耗尽不重试。超时明确记录 MODEL_REQUEST_TIMEOUT，服务端限流为 MODEL_RATE_LIMIT，服务端额度不足为 MODEL_QUOTA_EXHAUSTED，本地次数耗尽为 MODEL_REQUEST_BUDGET。
LIVE 业务流程、provider、hook 和 Host 共用从 worker 开始执行计算的截止时间；排队不消耗运行时限。离线 120 秒和冻结评测不变。Host 进程有额外 30 秒用于退出和保存证据，该宽限不会授权新的模型或业务动作。运行摘要保存实际 limits 和脱敏 request_failures。
普通插件 hook 作为另一层保护，不再声称该 hook 本身能够覆盖辅助请求。
全局请求额度在 `configs/model_usage.local.json` 持久预留。进程异常终止且缺完整计数时，按整次分配保守扣除。启动并发预算锁被占用时拒绝，不自动清空预算。
`max_total_requests` 为正整数时继续施加累计上限，显式 `null` 时仅保留累计记账与每运行上限。示例仍默认禁用 LIVE；启用须填写授权、模型/上游配置与有限的单次输出/时间限制。
`model_requests` 是已预留的实际请求尝试数，包括失败/被取消的辅助请求，不能解释为全部已计费。`model_cost=null`。
SDK 缺少某个请求的 tokens 用量时，总 `model_tokens=null`，仅已收到的合计放在 `observed_model_tokens`；完整性见 `model_usage_complete`。

## 本机启用

先按项目根 README 恢复并构建固定版本 AGH，在官方工作台完成 Agnes 模型配置。
后端安装 `.[api,mcp]`；Node 与 AGH workspace dependencies 必須可用。
复制 `configs/model_budget.example.json` 到 gitignored 的 `configs/model_budget.local.json`，填写授权引用、有限请求/输出/时间上限、上游目录和已配置 AGH 凭据 home。示例默认禁用，不能把拥有 Key 当作授权。

```powershell
.\.venv\Scripts\python.exe scripts/probe_agh.py --config configs/model_budget.local.json
$env:WORLDGUARD_LIVE_CONFIG = (Resolve-Path configs/model_budget.local.json).Path
.\.venv\Scripts\python.exe -m worldguard.api
```

probe 实际加载官方 Host 与两个产品插件并连接本机 MCP，模型请求 0。
没有设置 `WORLDGUARD_LIVE_CONFIG` 时，独立 API 仍不需要 AGH、MCP 或 Key，LIVE 请求返回原有 503。

### 在当前工作台直接操作

`python scripts/launch.py --live-config configs/model_budget.local.json` 同时准备 API 与 8510 工作台。
已有 API 时复用；若它未启用 LIVE 则提示先重启，不会接管或覆盖其配置。
工作台的「开始 LIVE Agnes 测试」调用同一创建接口，固定 AgnesAGH/automatic；
「开始离线测试」保留规则流程。两种模式都由 API 持有任务，刷新或关闭页面不会重新创建运行。
HTTP 提交响应丢失时，保持同一配置再次点击会复用 request_id；不自动重试或降级为离线。
运行时刷新工具事件、地图和检查结果；取消后等待退出并封存报告。缺少用量时显示未知，运行中显示结算中。
现有模型请求总额继续累计；是否施加累计上限由本机显式配置决定，工作台不会清空历史或重置额度。

```json
{
  "config_id": "dual_route_stale",
  "request_id": "唯一请求ID",
  "runtime_mode": "LIVE_AGNES",
  "execution_mode": "automatic",
  "tester": "AgnesAGH"
}
```

LIVE 只支持 automatic。`runtime_mode=LIVE_AGNES` 总是由 AgnesAGH 编排；既有前端省略 tester 也可调用，后端保存的 tester 会规范为 AgnesAGH。
DETERMINISTIC 的测试员仍为 FixedCoverage / SeededRandom / AdaptiveRule。输入 AgnesAGH 与 DETERMINISTIC 不匹配时返回 422。
状态、事件、地图、路径和导出沿用既有接口。新增 `/api/v1/runs/{run_id}/agh` 返回会话引用、用量、nonce、投影轨迹哈希、工具调用与产品事件对应。

## 报告和取消

模型调用 finish 只冻结后续业务动作；AGH 完成、用量和轨迹验证后才封存最终报告。自动 LIVE 缺少完整候选覆盖、最后审计通过或明确停止时标 BLOCKED。
取消先阻止下一业务动作，再结束 AGH 子进程；退出后保存已有几何结果和未知/已知用量。取消请求可能先返回 CANCELLED，报告稍后才可下载。超时、路由或模型错误记为基础设施问题。
报告保留原始 FAIL；SAFE_STOP 不算 REACHED。服务重启后历史保持只读。

## 已验收和未完成

`scripts/live_acceptance.py` 实际启动 HTTP 服务并创建真实 LIVE 运行，验证 nonce、故障恢复/停止、所有候选覆盖、地图、报告、ZIP 与轨迹哈希。逐条命令与真实结果见 `evidence/batches/AGH_LIVE/`。
执行路径已覆盖堵路、净空不足和目标断连。没有公平 Agent 增量实验、独立第三方终验、最终合作者前端验收、视频或实机证据；不能宣称 Agent 优于规则或已完成赛事交付。
本轮保留了初次接入失败、总结超时和候选覆盖不足的记录。早期快照的 token 数是已观察到的用量，不保证包括缺失辅助请求；后续版本显式区分完整与已观察用量。
