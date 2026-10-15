# WorldGuard 导航验收报告

- run_id：run_859fa203c0694bc998dd13051d6d881c / case_id：block_2002
- runtime_mode：DETERMINISTIC；执行：COMPLETED
- 待测对象：reference_safe_astar；场景：SYNTHETIC_GEOMETRIC
- 当前地图/任务/路径/约束哈希：{'environment_hash': 'ce821546475eadae514f43a37ae76c555b5b1460b2680626aafecf8be52e9428', 'task_hash': '8ce96eef23ed5aefaa9a582eea873d7111953c977ce554ce34a9c6fd65a98e2b', 'constraints_hash': '4bc586a281dab2b018eeb1292363202e80bf91042be1e062b638aa3e501bba93', 'path_hash': 'd844d76226b76bd0a25ea54f556d65fd809a4390fe884e0a2b197df5630be087', 'verifier_version': 'capsule-raw-grid-1'}
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
