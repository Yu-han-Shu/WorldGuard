# WorldGuard 导航验收报告

- run_id：run_cb2e2f68e0d44fdc8c1df232596d020a / case_id：block_2003
- runtime_mode：DETERMINISTIC；执行：COMPLETED
- 待测对象：reference_safe_astar；场景：SYNTHETIC_GEOMETRIC
- 当前地图/任务/路径/约束哈希：{'environment_hash': '2b4bd1415e6293ad9a739c07fe8b95ad1afe19fb34edfe15889bddb74ce07289', 'task_hash': '89c5461d8e7cc45243ebbe3bf787234d1ee7b522d6ab6c49dbdf08eab7ef7ac2', 'constraints_hash': '4bc586a281dab2b018eeb1292363202e80bf91042be1e062b638aa3e501bba93', 'path_hash': '58b0bd62f0acf255564c40c2d1a1b1cc6d570e4c41afd6aac0863f9156f447a3', 'verifier_version': 'capsule-raw-grid-1'}
- 原始候选审计：FAIL；原失败记录始终保留。
- 原始违规证据：[{'code': 'FOOTPRINT_COLLISION', 'segment_index': 11, 'segment_xy_m': ((3.875, 1.875), (4.125, 1.875)), 'centerline_distance_m': 0.125, 'obstacle_cell': (7, 17), 'obstacle_xy_m': (4.25, 1.875), 'kind': 'OBSTACLE', 'remaining_clearance_m': -0.10499999999999998}, {'code': 'FOOTPRINT_COLLISION', 'segment_index': 12, 'segment_xy_m': ((4.125, 1.875), (4.375, 1.875)), 'centerline_distance_m': 0.0, 'obstacle_cell': (7, 17), 'obstacle_xy_m': (4.25, 1.875), 'kind': 'OBSTACLE', 'remaining_clearance_m': -0.22999999999999998}, {'code': 'FOOTPRINT_COLLISION', 'segment_index': 13, 'segment_xy_m': ((4.375, 1.875), (4.625, 1.875)), 'centerline_distance_m': 0.0, 'obstacle_cell': (7, 17), 'obstacle_xy_m': (4.375, 1.875), 'kind': 'OBSTACLE', 'remaining_clearance_m': -0.22999999999999998}, {'code': 'FOOTPRINT_COLLISION', 'segment_index': 14, 'segment_xy_m': ((4.625, 1.875), (4.875, 1.875)), 'centerline_distance_m': 0.125, 'obstacle_cell': (7, 17), 'obstacle_xy_m': (4.5, 1.875), 'kind': 'OBSTACLE', 'remaining_clearance_m': -0.10499999999999998}]
- 恢复：REFRESH_MAP_REPLAN（同导航器）
- 恢复审计：PASS
- 导航：REACHED；reached=true；原因：REFRESH_MAP_REPLAN_VERIFIED
- 独立有限图 oracle：None
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
