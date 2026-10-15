# WorldGuard 导航验收报告

- run_id：run_9ac303f237164bb4bd4b78e5ef7005e8 / case_id：stop_4003
- runtime_mode：DETERMINISTIC；执行：COMPLETED
- 待测对象：reference_safe_astar；场景：SYNTHETIC_GEOMETRIC
- 当前地图/任务/路径/约束哈希：{'environment_hash': '0e7a4b29e10ed99baa492f3c8ce1c440e2133b9caeceac1fdf6d5e3bf8bdd2da', 'task_hash': '507715cffdaf36474daeaea51cf4d54d47c9328dd2b7ed2186613c782a00f7b6', 'constraints_hash': '4bc586a281dab2b018eeb1292363202e80bf91042be1e062b638aa3e501bba93', 'path_hash': 'e43204c1c1debbee4b0c2dcf706dc81c4897ecebb5bbfb8c7371246bb7648fec', 'verifier_version': 'capsule-raw-grid-1'}
- 原始候选审计：FAIL；原失败记录始终保留。
- 原始违规证据：[{'code': 'FOOTPRINT_COLLISION', 'segment_index': 10, 'segment_xy_m': ((3.625, 2.875), (3.875, 2.875)), 'centerline_distance_m': 0.125, 'obstacle_cell': (11, 16), 'obstacle_xy_m': (4.0, 2.875), 'kind': 'OBSTACLE', 'remaining_clearance_m': -0.10499999999999998}, {'code': 'FOOTPRINT_COLLISION', 'segment_index': 11, 'segment_xy_m': ((3.875, 2.875), (4.125, 2.875)), 'centerline_distance_m': 0.0, 'obstacle_cell': (11, 16), 'obstacle_xy_m': (4.0, 2.875), 'kind': 'OBSTACLE', 'remaining_clearance_m': -0.22999999999999998}, {'code': 'FOOTPRINT_COLLISION', 'segment_index': 12, 'segment_xy_m': ((4.125, 2.875), (4.375, 2.875)), 'centerline_distance_m': 0.0, 'obstacle_cell': (11, 16), 'obstacle_xy_m': (4.125, 2.875), 'kind': 'OBSTACLE', 'remaining_clearance_m': -0.22999999999999998}, {'code': 'FOOTPRINT_COLLISION', 'segment_index': 13, 'segment_xy_m': ((4.375, 2.875), (4.625, 2.875)), 'centerline_distance_m': 0.125, 'obstacle_cell': (11, 16), 'obstacle_xy_m': (4.25, 2.875), 'kind': 'OBSTACLE', 'remaining_clearance_m': -0.10499999999999998}]
- 恢复：REFRESH_MAP_REPLAN（同导航器）
- 恢复审计：UNKNOWN
- 导航：SAFE_STOP；reached=false；原因：NO_PATH_IN_FINITE_GRAPH
- 独立有限图 oracle：{'model': 'four_neighbor_cell_centers_exact_endpoint_edges_v1', 'visited': 308, 'scope': 'finite grid graph only; not arbitrary continuous or physical reachability', 'status': 'UNREACHABLE', 'reason': 'EXHAUSTIVE_GRAPH_SEARCH'}
- 汇总结论：FAILURES_FOUND，仅限该案例、固定机器人与离散运动图。
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
