# R08 复核结论

历史快照：以下结论属于 2026-10-12 R08。2026-10-13 已完成真实 Agnes 最小业务链路，见 AGH_LIVE.md 和 RELEASE_READINESS.md；完整独立终验仍未执行。

**完整参赛 MVP：NOT_READY；离线候选版：READY_WITH_LIMITATIONS。**
本轮由同一 Codex 执行者做第二遍复核，没有独立审查者，不能标“独立终验通过”。

## 已实际检查

- 64 项单元/集成/附加解析几何测试通过；lint 和 Python 编译检查通过。
- 附加 8 项测试以解析距离、原始坐标与固定半径确定期望值，不用生产验收器给自身生成真值。
- 连续路径薄墙、切线、角点、足迹边界、unknown、空路径、NaN、终点不变和过期凭据均覆盖。
- E1 原始结果重算一致，8 个危险候选重放一致；SAFE_STOP 和 REACHED 分列。
- 官方 AGH 上游工作树仍干净；旧导航源码未复制。
- 工作台真实浏览器运行/恢复/停止/刷新/切运行/下载已操作；图像不是生成的示意图。
- 候选包按白名单生成，扫描密钥模式和私人路径，校验 ZIP 路径与逐文件哈希。
- 干净安装的 8 条命令全部退出 0；第二目录的完整测试、演示、重放与重算 4 条命令全部退出 0，见 R07/R08 的 clean_commands.json。

## 未解决项

| 等级 | 问题 | 位置/证据 | 最短后续 |
|---|---|---|---|
| P1 | 真实 Agnes 业务闭环缺失；桥接仅离线预检与明确阻塞 | src/worldguard/agh_bridge.py；R01/R04 | 核实项目 route，完成限额与 wg-only 会话，批准 smoke 后实跑 |
| P1 | E2 四方法 Agent 比较未执行，部分真值指标 null | docs/EVALUATION.md | LIVE 后单独批准评测预算，冻结新实验 |
| P1 | 独立审查未执行，视频/声明/赛事政策未确认 | AI_USAGE、HUMAN_ACTIONS | 独立会话或人员复核；用户完成材料 |
| P2 | UI 取消仅验证核心行为，浏览器未捕捉进行中操作 | UI_VERIFICATION.md | 用可控长任务做一次实际取消演示 |
| P2 | 旧导航适配与 POSIX 未测 | LIMITATIONS.md | 权限/环境明确后另批验证 |

未观察到危险路径错误放行或秘密入包，不等于数学完备性或渗透测试结论。
冻结 E1 后只调整 AGH 默认 profile 和构建依赖；数值计算源文件未改变，记录见 experiments/final_v1/post_freeze_changes.json。
仍使用 candidate 命名，不生成正式 release.zip；不自动上传或提交。
