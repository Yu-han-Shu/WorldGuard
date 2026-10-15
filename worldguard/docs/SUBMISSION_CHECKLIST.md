# 提交材料状态（2026-10-15）

| 必填项 | 交付位置与内容 |
|---|---|
| 基本信息 | 项目报告：名称、方向、摘要、问题来源与目标 |
| 技术信息 | 技术指南：AGH、模型 ID/环节/调用、数据与软件环境 |
| 可运行作品 | 公开 GitHub、源码快照、安装与复现说明 |
| 演示视频 | B站 04:15，2026-10-15 10:48:05 发布 |
| 运行证据 | 两组真实 Host 记录；工具 ID 对应的调用链、Agnes 请求、配置与验收 |
| 测试样例 | 正常、边界、失败与恢复三类；三例重放 matches=true |
| 成员声明 | 独立 PDF，职责已列，已列团队职责与正式声明 |
| 公开内容 | B站有效链接及显示发布日期的真实截图 |

公开仓库：https://github.com/Yu-han-Shu/WorldGuard
视频：https://www.bilibili.com/video/BV1dQJ66tEsV/
干净 Linux CI：https://github.com/Yu-han-Shu/WorldGuard/actions/runs/38674318227

CI 已完成依赖安装、178 项 Python、15 项保护层测试、前端 6 PASS / 1 SKIP 与生产构建。Windows 发布副本亦通过 178 项 Python 检查。
三类样例使用保存的 Strategy A* 参数重放；原始记录不改写。MOCK、离线重放与真实模型执行分别说明。
未覆盖实机实验、独立第三方终验、新机完整 LIVE 交互及公平预算下 Agent 优势对照。
ZIP 按本科生组-U406-零界智行-束宇涵命名；视频按要求仅交链接。本状态不表示官网已提交。
