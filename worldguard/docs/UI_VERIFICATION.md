# 浏览器实际操作记录

2026-10-12 Asia/Shanghai，本机 Codex 浏览器打开 127.0.0.1:8510，实际执行：

- 双通道绕行、陈旧视图、FixedCoverage；生成 run_1482f0be638c4d1983d8de4d93d1d9f5。
- normal 为 PASS；block_route_1 显示原始 FAIL、恢复 PASS、REACHED。真实截图 ui-recovery.png。
- 实际点击“导出完整证据 ZIP”，下载成功；包含对应运行原始 JSON/Markdown/事件。
- 刷新页面后同一 run 仍可查看；没有触发新运行。
- 切到单入口目标区，新运行 run_39fcf3c104d24beea02c01caff6178d7：1 到达、1 SAFE_STOP。
- disconnect_goal_1 显示原始 FAIL、恢复 UNKNOWN、reached=false、INCONCLUSIVE_STOP；截图 ui-safe-stop.png。
- LIVE 按钮实际禁用。

截图位于本地 artifacts/batches/R05。UI 取消的点击时机未覆盖（本地小任务很快），取消状态机已有自动测试；不宣称该交互已经浏览器验收。
初次发现任务完成后开始按钮保持禁用：fragment 完成时改为整页刷新；已在浏览器复核并成功启动第二个 run。
