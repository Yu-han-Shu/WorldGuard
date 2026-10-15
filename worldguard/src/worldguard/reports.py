def markdown_report(result):
    original, recovery = result["original_audit"], result.get("recovery_audit")
    return f"""# WorldGuard 导航验收报告

- run_id：{result["run_id"]} / case_id：{result["case_id"]}
- runtime_mode：{result["runtime_mode"]}；执行：{result["execution_status"]}
- 待测对象：{result.get('original_plan', {}).get('planner_name', 'reference_safe_astar')}；策略参数：{result.get('navigation_strategy')}；提交：{result.get('submission_id')}；场景：SYNTHETIC_GEOMETRIC
- 当前地图/任务/路径/约束哈希：{original.get("binding")}
- 原始候选审计：{original["status"]}；原失败记录始终保留。
- 原始违规证据：{original["violations"]}
- 恢复：{"REFRESH_MAP_REPLAN（同导航器）" if recovery else "未执行"}
- 恢复审计：{recovery["status"] if recovery else "NOT_RUN"}
- 导航：{result["navigation_status"]}；reached={str(result["reached"]).lower()}；原因：{result["reason_code"]}
- 独立有限图 oracle：{result.get("oracle")}
- 汇总结论：{result["verdict"]}，仅限该案例、固定机器人与离散运动图。
- SUT 执行：{result["sut_executions"]}；模型请求：{result["model_requests"]}；tokens/费用：null（未调用/未测）
- 相切拒绝；epsilon={original["epsilon_m"]} m；unknown 阻塞。

## 复现

在项目目录使用 `python -m worldguard.cli replay --case-dir CASE_DIRECTORY --out NEW_OUTPUT_DIRECTORY`。
同目录 scene_before/after、task、fault、plan、audit、result 与 manifest 构成自包含案例。
清单用于检测文件改动，不是数字签名或对抗恶意伪造的认证。

## 限制

这是部署前二维几何仿真，不是实机、动力学、制动安全或安全认证。
SAFE_STOP 不等于 REACHED；危险候选被拒绝不表示真实发生碰撞。
此确定性工作流不能证明 Agnes 自主选例价值。原始规划耗时见 JSON。
"""
