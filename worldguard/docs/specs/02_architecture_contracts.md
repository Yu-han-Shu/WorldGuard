# 架构、工具与状态契约 v1

本文件是拟实现接口，不是 AGH 官方 API。产品工具统一使用 `wg_` 前缀，具体 SDK 注册方式按执行环境实际版本实现。

## 1. 最小架构

```text
本地工作台
    └─ CampaignRunner：状态、预算、事件、取消、目录边界
         ├─ Fixed / Random / AdaptiveRule 基线（无模型）
         └─ 官方 AGH + Agnes → 受控 MCP 工具
                  ├─ SceneFactory / 故障目录
                  ├─ NavigationAdapter（待测对象 SUT）
                  ├─ 独立几何审计器
                  └─ EvidenceStore / ReportBuilder
```

不实现第二套 LLM tool-call 循环。UI 通过经过核实的 AGH CLI/接口启动会话，Agnes 在 AGH 中决定调用工具；Python 服务只执行业务工具和预算约束。不能只调用一次 `run_everything()`，再让模型讲解。

默认技术：Python 3.11 + NumPy/SciPy + pytest + 轻量本地页面（优先 Streamlit）+ 官方 Python MCP SDK。Open3D 为可选导入，不阻断纯二维测试。版本通过真实安装/锁文件固定，不照抄猜测版本。

## 2. 目录建议

```text
worldguard/
  pyproject.toml
  src/worldguard/
    contracts.py
    scene.py
    faults.py
    planners/{base.py,reference_astar.py,legacy_adapter.py}
    verifier/{geometry.py,audit.py}
    campaign/{runner.py,baselines.py,state.py}
    mcp_server.py
    agh_bridge.py
    reports.py
    cli.py
  app.py
  scenarios/dev/
  configs/{default.json,model_budget.example.json}
  tests/{unit,integration,e2e}/
  scripts/{doctor.py,launch.py,package_release.py}
  docs/{STATE.md,HANDOFF.md,DECISIONS.md,SOURCES.md}
  artifacts/                    # 原始运行记录，默认不进发布包
```

若已有等价结构，记录映射，不为符合树形而重写。禁止引入不必要的 Redis、消息队列或微服务。

## 3. 固定数据定义

- `Scene`：schema_version、scene_id、revision、origin_xy_m、resolution_m、width、height、原始 occupied/unknown cells、content_hash。
- `RobotSpec`：圆盘半径 radius_m、安全余量 clearance_margin_m、endpoint_tolerance_m、约束哈希；本轮禁止改变。
- `Task`：task_id、start_xy_m、goal_xy_m、RobotSpec、scene_id；起终点固定。
- `CaseSpec`：case_id、父场景哈希、故障种类、合法故障参数、seed、fault_hash；重复运行必须还原相同条件。
- `PlanResult`：SUT 名称/版本、规划所见地图哈希、路径点列表及 path_hash、终点偏移、成功/失败代码、计算耗时。
- `AuditResult`：当前真实地图哈希、路径哈希、约束哈希、verifier_version、PASS/FAIL/UNKNOWN、违规线段/坐标、中心线距离和足迹余量、起终点误差。
- `Campaign`：run_id、模式、case 预算、重试预算、总耗时上限、模型调用/计费用量、状态、事件序列。

禁止 NaN/Infinity，所有数值有限且有单位；缺失数据为 null，不用 0 伪装。

网格规范：`row` 对 y、`col` 对 x；世界坐标到 cell 用 floor；cell 中心为 `origin + (index + 0.5)*resolution`。旧实现坐标约定不同，适配时显式转换并测试，不静默混用 round/floor。

## 4. 业务工具（R04 完成）

| 工具 | 最小输入 | 最小输出/副作用 |
|---|---|---|
| `wg_health` | nonce | 原样 nonce、服务版本、仅目录标识 |
| `wg_create_campaign` | 已批准的 config_id | run_id、冻结预算/约束哈希 |
| `wg_list_candidates` | run_id、已知过滤条件 | 有限合法案例描述，不含未来结果/答案标签 |
| `wg_run_case` | run_id、case_id、request_id | 原始待测路径/错误及证据 ID；不内置自动恢复 |
| `wg_audit_path` | run_id、case_id、path_id | 当前地图上的独立验收结果 |
| `wg_recover_case` | run_id、case_id、有限 action、依据 evidence_ids、request_id | 新候选路径或明确停止状态；不能自行判安全 |
| `wg_rerun_case` | run_id、case_id、request_id | 相同 seed/版本/故障条件的确定性重放 |
| `wg_read_evidence` | run_id、evidence_id | 白名单内证据摘要，不读取任意文件 |
| `wg_finish_campaign` | run_id | 从原始结果重算的报告与相对路径 |
| `wg_stop_campaign` | run_id、原因代码 | 取消后续任务、保留已有记录 |

调用产生的 ID 不能由模型随意捏造。`run_id` 绑定该会话工作区；无权访问其他 run。路径只由服务端拼接，不接受任意绝对路径、URL 或代码。

## 5. 受控恢复

P0 action 仅允许：`REFRESH_MAP_REPLAN`、`RETRY_TRANSIENT_ONCE`、`SAFE_STOP`。

更新地图重规划必须使用同一物理真值、任务和约束；不得删除障碍、减小机器人半径、调低安全余量或转移终点。可选 `REFERENCE_REPLAN` 只能以明确标识的备用导航器执行；其成功不能计为原 SUT 已修复。

重试复用 request_id；同 ID 同内容返回既有结果，内容变化返回冲突。默认一个 campaign 串行执行，无并发写同一状态。

## 6. 三层状态不能混写

- 工程执行：`RUNNING / COMPLETED / BLOCKED / CANCELLED / ERROR`。
- 导航结果：`REACHED / SAFE_STOP / UNSAFE_CANDIDATE / NOT_RUN / INCOMPLETE`。
- 路径审计：`PASS / FAIL / UNKNOWN`。

一条危险候选被拦截，表示守卫发挥作用，不代表任务到达；源导航器仍有失败记录。恢复成功后历史失败不可改写为通过。

报告汇总只用 `BOUNDED_PASS / FAILURES_FOUND / INCONCLUSIVE`：完成规定测试且未发现失败可写 BOUNDED_PASS，必须附测试范围，不得写“系统已经安全认证”。

## 7. 生命周期和预算

默认模型调用关闭；R00 记录用户已批准额度后才能开启。开发 smoke 最多一个小任务；具体请求上限与费用限额写入本地配置，不在本包假定额度。

一旦批准，建议默认每案例最多 2 次恢复尝试、每 campaign 最多 12 个计费案例动作，模型请求和实际 tokens 单独记账。重放、恢复、审计是否计入各预算由评测协议预先固定，不能在结果出来后调整。

连接失败、非 Agnes 路由、超预算、工作区逃逸必须拒绝。能提前拦截请求时先检查预算；无法保证 token 精确限额时用保守请求数和最大输出上限并标明限制，不宣称已精确控费。
