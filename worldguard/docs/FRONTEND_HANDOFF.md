# WorldGuard 前端交接：HTTP API v1

## 2026-10-13 导航优化更新

capabilities.features.strategy_optimization=true 时可展示独立优化入口。
POST `/api/v1/runs/{run_id}/cases/{case_id}/optimize` 创建或返回同一案例缓存结果；
GET 对应 `/optimization` 读取结果，无结果返回 404 OPTIMIZATION_NOT_READY，自动任务活跃时返回 409 AUTOMATIC_RUN_BUSY。
客户端提供 `optimizeCase` / `optimization`，强类型 `OptimizationView` 包括全部候选的原始计划、独立审计、长度/转弯/净空和评分。
评分固定为长度 + 0.25 × 转弯次数 + 1 / (1 + 非负剩余净空)。候选仅在规划成功且独立审计 PASS 时参与选择。
IMPROVED 只代表本案例评分下降；NO_IMPROVEMENT 保留基线；NO_SAFE_PATH 代表本次候选未找到安全路径，不能当作不可达证明。
四候选比较是确定性算法、模型请求 0；不是多 Agent 协作或 Agnes 自主优化。
优化使用故障后的当前原始地图，保留固定目标与足迹；原测试报告、事件与导航次数不被改写。证据追加到 optimization/{case_id}.json 并包含于 ZIP。
RunView.execution_error 为脱敏错误码，可用于解释模型/服务未完成，不能当作导航缺陷。

## 2026-10-13 LIVE 后端更新

前端由合作者负责。原路由继续可用；已补受限真实 Agnes 执行。
检查 capabilities 的 LIVE_AGNES.available；仅配置并授权后端时开放。默认离线安装无需 Key。
LIVE 创建时使用 runtime_mode=LIVE_AGNES、execution_mode=automatic，测试员规范为 AgnesAGH。
新增 GET `/api/v1/runs/{run_id}/agh` 和客户端 `aghSession(runId)`，以及 RunView/ReportView.agh_session。
用量完整性由 model_usage_complete 标识，缺总用量时 model_tokens=null，已观察值在 observed_model_tokens。
取消立即阻止后续工具；LIVE 报告需等子进程退出后才能下载。
详见 [真实链路说明](AGH_LIVE.md)；OpenAPI/类型已经更新。以下内容为初次离线交接记录，旧“LIVE 未开放”描述不再适用于已授权配置的后端。

2026-10-13；分支 `codex/worldguard-execution`。本轮暂停真实 Agnes 接入，优先交付独立前端可用后端。
入口见 [frontend/README.md](../frontend/README.md)，字段定义以 [OpenAPI](../frontend/openapi.json) 和 [TypeScript 类型](../frontend/schema.d.ts) 为准。

## 页面建议

1. 测试配置：场景、当前/陈旧地图视图、测试员、自动/手动模式、开始按钮。
2. 运行列表和详情：运行状态、预算、到达/停止数、案例列表、事件时间线。
3. 案例地图：原始/注入障碍、固定起终点、原始/恢复路径、违规线段、审计证据。
4. 结果和导出：保留原始失败，显示恢复结果，下载 JSON/Markdown/ZIP。

## 路由

所有 JSON API 前缀 `/api/v1`，成功体直接返回数据；错误统一 `{error:{code,message,details?}}`。

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/health` | 服务状态、版本、模型调用是否开启 |
| GET | `/capabilities` | 可用模式、测试员、恢复动作、未来能力开关 |
| GET | `/configs` | 六个批准配置及预算 |
| POST | `/runs` | 创建运行，自动执行或等待手动动作，201 |
| GET | `/runs?offset=0&limit=50` | 按运行目录更新时间倒序分页，limit ≤100 |
| GET | `/runs/{run_id}` | 状态、后台任务、只读/中断标记、链接 |
| POST | `/runs/{run_id}/stop` | 取消后续动作并保存报告，body `{}` 即可 |
| POST | `/runs/{run_id}/finish` | 手动运行结束；汇总现有证据，不自动补做动作 |
| GET | `/runs/{run_id}/candidates` | 有限候选 ID，不含未来结果标签 |
| GET | `/runs/{run_id}/cases/{case_id}` | 两版地图、任务、所有路径与审计、最终结果 |
| GET | `/runs/{run_id}/cases/{case_id}/map.svg` | 后端生成的真实地图，可直接 img 展示 |
| POST | `/runs/{run_id}/cases/{case_id}/run` | 原始路径，body `{request_id}` |
| POST | `/runs/{run_id}/cases/{case_id}/audit` | 独立审计，body `{path_id}` |
| POST | `/runs/{run_id}/cases/{case_id}/recover` | 有依据的恢复，见下面流程 |
| POST | `/runs/{run_id}/cases/{case_id}/rerun` | 原始条件复测，body `{request_id}` |
| GET | `/runs/{run_id}/events?cursor=0&limit=100` | 增量事件；limit ≤500 |
| GET | `/runs/{run_id}/evidence/{evidence_id}` | 已签发证据内容；不可读取任意路径 |
| GET | `/runs/{run_id}/report` | 最终 JSON 报告 |
| GET | `/runs/{run_id}/report.md` | 下载 Markdown |
| GET | `/runs/{run_id}/export` | 下载原始证据 ZIP |

另有 `/docs`、`/redoc` 和 `/openapi.json`。下载链接是后端绝对地址，不要发往前端开发服务器。

## 自动测试

```json
{
  "config_id": "dual_route_stale",
  "request_id": "create_example_001",
  "runtime_mode": "DETERMINISTIC",
  "execution_mode": "automatic",
  "tester": "AdaptiveRule",
  "seed": 101
}
```

`config_id` 从 `/configs` 获取。`seed` 仅控制选例器，场景 seed 由批准配置冻结。
创建返回 `RunView`，ID 在 `state.run_id`。返回前小任务可能已经完成，不假定一定 RUNNING。
每 0.5–1 秒 GET 状态与事件；`job_active=false` 后停止轮询后台执行状态。
`report_available=true` 才请求报告/下载，提前请求返回 409。
事件 cursor 是已消费的条数，保存服务返回的 `next_cursor`；`has_more=true` 时继续拉取。
读取接口不消费业务动作预算，也不追加工具事件。事件只包含哈希和 ID，详情从 case/evidence 查询。

## 手动调试

创建时 `execution_mode=manual`，然后：

1. GET candidates，选真实 `case_id`；POST run，保存 `path_id`。
2. POST audit，保存 `evidence_id`。规划成功不是验收通过。
3. 若 FAIL/UNKNOWN，可 POST recover：

```json
{
  "action": "REFRESH_MAP_REPLAN",
  "evidence_ids": ["从 audit 响应取得的 evidence_id"],
  "request_id": "recover_example_001"
}
```

4. 恢复返回新路径，必须再次 audit。无法通过可 `action=SAFE_STOP`，引用最新审计证据。
5. POST finish，保留原失败，返回最终报告。未审计的路径仍是 UNKNOWN，不会自动补验收。

`RETRY_TRANSIENT_ONCE` 是预留动作，当前确定性导航器返回 `NO_TRANSIENT_FAILURE_TO_RETRY`。
自动任务执行期间手动动作返回 `AUTOMATIC_RUN_BUSY`，取消始终可请求。
同一动作同 request_id/同内容幂等；同 ID 不同内容返回冲突。不同动作请用新 ID。
创建请求的去重记录随运行保存，重启后复用 request_id 返回原运行；动作的写会话不跨重启恢复。

## 地图和状态约定

- 世界坐标单位米，x 向右、y 向上；二维数组 cell 为 `[row,col]`，不是 `[x,y]`。
- cell 中心：`origin + (index + 0.5) * resolution`。Canvas y 轴需翻转。
- occupied/unknown 都视为阻塞；障碍为整个 cell 矩形。未知区域也应在前端标识。
- 圆形足迹使用 `radius_m + clearance_margin_m`；起终点、半径和阈值不能从前端修改。
- `paths[]` 包含 `role=original/rerun/recovery`、path_id、plan.path、独立 audit、违规线段坐标。
- 运行状态 `RUNNING/COMPLETED/BLOCKED/CANCELLED/ERROR` 与导航 `REACHED/SAFE_STOP/INCOMPLETE` 分开。
- 审计 `PASS/FAIL/UNKNOWN`；未审计显示 `NOT_RUN`。原始 FAIL 在恢复成功后仍显示 FAIL。
- `SAFE_STOP` 不表示到达；当前工作流停止是 `INCONCLUSIVE_STOP`，不声称证明连续空间不可达。
- 最终 verdict 只用 `BOUNDED_PASS/FAILURES_FOUND/INCONCLUSIVE`，不要写“安全认证”。

## 扩展约定

前端通过 capabilities 控制入口，不猜测功能是否存在。LIVE 模式现在返回 503，不能静默降级。
后续 Agnes 会复用运行、案例、事件和报告接口；tokens/费用未知时使用 null。
`read_only=true` 表示服务重启前或其他入口创建的运行，能看历史，不能追加动作；新建运行即可继续测试。
`interrupted=true` 表示重启前未结束，展示 BLOCKED，不篡改磁盘里的原始 RUNNING 记录。
刷新页面不取消任务，只有明确 stop 请求才取消；取消阻止下一动作，当前规划最多约 10 秒。
历史 legacy 路径的 `historical_original/recovery` 只供显示，不能送回写接口。
当前为单进程本地服务；不要用多 worker 或开发自动重载执行运行中的任务。

## 常见错误

| HTTP / code | 前端处理 |
|---|---|
| 422 VALIDATION_ERROR / INVALID_ID / CONFIG_NOT_APPROVED | 展示字段错误，重新获取配置 |
| 404 RUN_NOT_FOUND / CASE_NOT_FOUND / UNKNOWN_PATH / EVIDENCE_NOT_FOUND | 提示对象不存在，刷新列表 |
| 409 REQUEST_ID_CONFLICT | 不要自动生成新 ID 重试未知结果；核对原操作 |
| 409 AUTOMATIC_RUN_BUSY / CAMPAIGN_NOT_RUNNING | 刷新运行状态，更新按钮 |
| 409 RUN_READ_ONLY_AFTER_RESTART | 展示历史只读，提供新建运行 |
| 409 REPORT_NOT_READY | 继续等待报告 |
| 409 SUT_BUDGET_EXHAUSTED / WALL_TIME_BUDGET_EXHAUSTED | 停止追加动作，结束并展示已有结果 |
| 503 LIVE_NOT_AVAILABLE | 显示“真实 Agnes 尚未开放” |
| 500 INFRASTRUCTURE_ERROR | 显示服务错误，不计作导航算法缺陷 |

真实密钥只配置在后端运行环境；这个前端契约不需要 Key。没有远程部署、账户鉴权、实机控制或模型付费调用。
