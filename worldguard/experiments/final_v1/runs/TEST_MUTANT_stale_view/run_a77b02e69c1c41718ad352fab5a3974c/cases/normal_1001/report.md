# WorldGuard 导航验收报告

- run_id：run_a77b02e69c1c41718ad352fab5a3974c / case_id：normal_1001
- runtime_mode：DETERMINISTIC；执行：COMPLETED
- 待测对象：reference_safe_astar；场景：SYNTHETIC_GEOMETRIC
- 当前地图/任务/路径/约束哈希：{'environment_hash': 'acde9874df48f66506bf49173c4875345185137fcbf1dc0d0fca0aab3206265c', 'task_hash': '5bf16fd84fb0b8fff46d8cff9f9c06ff6f2f3e13546a57218d1b3ef5fb3f559e', 'constraints_hash': '4bc586a281dab2b018eeb1292363202e80bf91042be1e062b638aa3e501bba93', 'path_hash': '58b0bd62f0acf255564c40c2d1a1b1cc6d570e4c41afd6aac0863f9156f447a3', 'verifier_version': 'capsule-raw-grid-1'}
- 原始候选审计：PASS；原失败记录始终保留。
- 原始违规证据：[]
- 恢复：未执行
- 恢复审计：NOT_RUN
- 导航：REACHED；reached=true；原因：VERIFIED_ORIGINAL
- 独立有限图 oracle：None
- 汇总结论：BOUNDED_PASS，仅限该案例、固定机器人与离散运动图。
- SUT 执行：1；模型请求：0；tokens/费用：null（未调用/未测）
- 相切拒绝；epsilon=1e-09 m；unknown 阻塞。

## 复现

在项目目录使用 `python -m worldguard.cli replay --case-dir CASE_DIRECTORY --out NEW_OUTPUT_DIRECTORY`。
同目录 scene_before/after、task、fault、plan、audit、result 与 manifest 构成自包含案例。
清单用于检测文件改动，不是数字签名或对抗恶意伪造的认证。

## 限制

这是部署前二维几何仿真，不是实机、动力学、制动安全或安全认证。
SAFE_STOP 不等于 REACHED；危险候选被拒绝不表示真实发生碰撞。
此确定性工作流不能证明 Agnes 自主选例价值。原始规划耗时见 JSON。
