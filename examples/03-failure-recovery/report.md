# WorldGuard 导航验收报告

- run_id：run_71c6c2cf8f6d476e98496876c644203d / case_id：block_route_2
- runtime_mode：LIVE_AGNES；执行：COMPLETED
- 待测对象：strategy_astar；策略参数：{'schema_version': 'worldguard-strategy/v1', 'planner': 'strategy_astar', 'turn_cost_m': 0.25, 'clearance_weight': 0}；提交：submission_417733cfbb6f34e3603ae79b；场景：SYNTHETIC_GEOMETRIC
- 当前地图/任务/路径/约束哈希：{'environment_hash': '70025a046a220b165f57252a6fd602e351635db4d4d0e904ad0564ce1b0eaec1', 'task_hash': '5b3e29d89bd9a979f77753e3624065fa799e18e7ab839203903ebcfb2bbc6ce4', 'constraints_hash': '4bc586a281dab2b018eeb1292363202e80bf91042be1e062b638aa3e501bba93', 'path_hash': '21967d507c55ca77f897b0de588f88130117156e9505ef37b095eb79a5a843fe', 'verifier_version': 'capsule-raw-grid-1'}
- 原始候选审计：FAIL；原失败记录始终保留。
- 原始违规证据：[{'code': 'FOOTPRINT_COLLISION', 'segment_index': 80, 'segment_xy_m': ((10.625, 10.875), (10.875, 10.875)), 'centerline_distance_m': 0.125, 'obstacle_cell': (43, 44), 'obstacle_xy_m': (11.0, 10.875), 'kind': 'OBSTACLE', 'remaining_clearance_m': -0.10499999999999998}, {'code': 'FOOTPRINT_COLLISION', 'segment_index': 81, 'segment_xy_m': ((10.875, 10.875), (11.125, 10.875)), 'centerline_distance_m': 0.0, 'obstacle_cell': (43, 44), 'obstacle_xy_m': (11.0, 10.875), 'kind': 'OBSTACLE', 'remaining_clearance_m': -0.22999999999999998}, {'code': 'FOOTPRINT_COLLISION', 'segment_index': 82, 'segment_xy_m': ((11.125, 10.875), (11.375, 10.875)), 'centerline_distance_m': 0.0, 'obstacle_cell': (43, 44), 'obstacle_xy_m': (11.125, 10.875), 'kind': 'OBSTACLE', 'remaining_clearance_m': -0.22999999999999998}, {'code': 'FOOTPRINT_COLLISION', 'segment_index': 83, 'segment_xy_m': ((11.375, 10.875), (11.625, 10.875)), 'centerline_distance_m': 0.0, 'obstacle_cell': (43, 45), 'obstacle_xy_m': (11.375, 10.875), 'kind': 'OBSTACLE', 'remaining_clearance_m': -0.22999999999999998}, {'code': 'FOOTPRINT_COLLISION', 'segment_index': 84, 'segment_xy_m': ((11.625, 10.875), (11.875, 10.875)), 'centerline_distance_m': 0.125, 'obstacle_cell': (43, 45), 'obstacle_xy_m': (11.5, 10.875), 'kind': 'OBSTACLE', 'remaining_clearance_m': -0.10499999999999998}]
- 恢复：REFRESH_MAP_REPLAN（同导航器）
- 恢复审计：PASS
- 导航：REACHED；reached=true；原因：VERIFIED
- 独立有限图 oracle：None
- 汇总结论：FAILURES_FOUND，仅限该案例、固定机器人与离散运动图。
- SUT 执行：2；模型请求：None；tokens/费用：null（未调用/未测）
- 相切拒绝；epsilon=1e-09 m；unknown 阻塞。

## 复现

在项目目录使用 `python -m worldguard.cli replay --case-dir CASE_DIRECTORY --out NEW_OUTPUT_DIRECTORY`。
同目录 scene_before/after、task、fault、plan、audit、result 与 manifest 构成自包含案例。
清单用于检测文件改动，不是数字签名或对抗恶意伪造的认证。

## 限制

这是部署前二维几何仿真，不是实机、动力学、制动安全或安全认证。
SAFE_STOP 不等于 REACHED；危险候选被拒绝不表示真实发生碰撞。
此确定性工作流不能证明 Agnes 自主选例价值。原始规划耗时见 JSON。
