# WorldGuard 导航验收报告

- run_id：run_3f3ab71f9ba64d908d71982d1df57172 / case_id：clearance_3002
- runtime_mode：DETERMINISTIC；执行：COMPLETED
- 待测对象：reference_safe_astar；场景：SYNTHETIC_GEOMETRIC
- 当前地图/任务/路径/约束哈希：None
- 原始候选审计：UNKNOWN；原失败记录始终保留。
- 原始违规证据：[]
- 恢复：REFRESH_MAP_REPLAN（同导航器）
- 恢复审计：UNKNOWN
- 导航：SAFE_STOP；reached=false；原因：NO_PATH_IN_FINITE_GRAPH
- 独立有限图 oracle：{'model': 'four_neighbor_cell_centers_exact_endpoint_edges_v1', 'visited': 90, 'scope': 'finite grid graph only; not arbitrary continuous or physical reachability', 'status': 'UNREACHABLE', 'reason': 'EXHAUSTIVE_GRAPH_SEARCH'}
- 汇总结论：INCONCLUSIVE，仅限该案例、固定机器人与离散运动图。
- SUT 执行：2；模型请求：0；tokens/费用：null（未调用/未测）
- 相切拒绝；epsilon=1e-09 m；unknown 阻塞。

## 复现

在项目目录使用 `python -m worldguard.cli replay --case-dir CASE_DIRECTORY --out NEW_OUTPUT_DIRECTORY`。
同目录 scene_before/after、task、fault、plan、audit、result 与 manifest 构成自包含案例。
清单用于检测文件改动，不是数字签名或对抗恶意伪造的认证。

## 限制

这是部署前二维几何仿真，不是实机、动力学、制动安全或安全认证。
SAFE_STOP 不等于 REACHED；危险候选被拒绝不表示真实发生碰撞。
此确定性工作流不能证明 Agnes 自主选例价值。原始规划耗时见 JSON。
