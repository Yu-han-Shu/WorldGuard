# 来源、版本与赛事合规登记

**核对日期：2026-10-12。** 本包整理时检查了用户提供的材料、公开赛事通知和下列代码/官方文档。未运行用户仓库、AGH 或 WorldGuard，不把静态阅读当实测。

## 1. 来源目录

| ID | 来源 | 用途与证据边界 |
|---|---|---|
| U1 | 用户对话中的报名表与赛事通知 | 本科组、C/C4、AGH、Agnes-only、作品材料与截止日期；不是代用户报名证明 |
| U2 | 用户附件 `WorldGuard_高校组参赛项目梳理.md` | 旧版项目背景；本包采用后来确定的“部署前 AI 测试员”定位，覆盖旧版范围 |
| S1 | [江苏理工学院教务处赛事通知](https://jw.jsut.edu.cn/2026/0929/c3461a217560/page.htm) | 验证完整执行闭环、非独立方向奖项、学生独立完成与时间安排 |
| S2 | [旧导航代码](https://github.com/Yu-han-Shu/realityscan-uv3d-navigation/blob/802e179ab899e0cec11dcaee2b7c722c733613b4/robot_pipeline/navigation.py) | 当前静态检查的主要复用对象 |
| S3 | [旧验收代码](https://github.com/Yu-han-Shu/realityscan-uv3d-navigation/blob/802e179ab899e0cec11dcaee2b7c722c733613b4/robot_pipeline/validate_outputs.py) | 点采样检查、原数据依赖与新验收器设计边界 |
| S4 | [旧仓库 README](https://github.com/Yu-han-Shu/realityscan-uv3d-navigation/blob/802e179ab899e0cec11dcaee2b7c722c733613b4/README.md) | 路径与数据说明；历史成绩不能复制到新项目 |
| S5 | [AGH 安装指南](https://github.com/AgnesAI-Labs/agnes-harness/blob/dc267c3c78429933e2b3d8c5d544e56bb980a574/docs/guide/install.zh-CN.md) | 源码构建、平台依赖；执行机仍需实际验证 |
| S6 | [AGH MCP 指南](https://github.com/AgnesAI-Labs/agnes-harness/blob/dc267c3c78429933e2b3d8c5d544e56bb980a574/docs/guide/mcp.zh-CN.md) | stdio/HTTP/SSE、审核、连接与真实调用的区别 |
| S7 | [AGH 快速开始](https://github.com/AgnesAI-Labs/agnes-harness/blob/dc267c3c78429933e2b3d8c5d544e56bb980a574/docs/guide/quickstart.zh-CN.md) | home/profile、模型目录和 CLI 入口 |
| S8 | [MCP 官方构建服务指南](https://modelcontextprotocol.io/docs/2026-07-28/develop/build-server) | MCP 标准服务，stdio stdout 禁止日志；版本要实际核对 |
| S9 | [Nav2 Collision Monitor](https://docs.nav2.org/rolling/configuration_and_development/configuration_guide/core_servers/collision_monitor/configuring_collision_monitor_node/) | 现有导航生态已有碰撞监控；不能夸称填补整个避障空白 |
| S10 | [Nav2 行为树说明](https://docs.nav2.org/jazzy/getting_started/nav2_behavior_trees/detailed_behavior_tree_walkthrough/detailed_behavior_tree_walkthrough/) | 已有重规划/恢复背景，本项目重点是测试工作流 |
| S11 | [赛事官网](https://agnes-ai.cn/hackathon) | 具体提交入口和最新变更；本次静态抓取没有正文，不能据此复核评分细则 |

## 2. 已核对版本

旧导航仓库 commit：`802e179ab899e0cec11dcaee2b7c722c733613b4`。

- `navigation.py` blob：`4c91924a6f45770a170c89672d0d877d63fbd351`。
- `validate_outputs.py` blob：`1c1a00e7b47188cfccc57b30849d5bb04b53eb84`。

AGH 参考 commit：`dc267c3c78429933e2b3d8c5d544e56bb980a574`。这只是本包核对的源码版本，不保证用户机器运行成功。若改用新版，须记录变更、重做 smoke，再冻结。

官方安装文档所列构建环境为 Node >=24.10、pnpm 10.34.5；Linux/Windows 有额外平台依赖。不能把文档示例等同于已在本机验证，也不能仅复制 `agnes.mjs` 而遗漏运行目录。[S5]

## 3. 赛事硬约束与待核实项

用户提供通知明确：使用 AGH 作为运行与执行底座，全部模型调用仅限 Agnes，提交可运行作品/复现方式、3–5 分钟视频、运行验证证据、成员分工和独立完成声明；旧代码和素材需说明来源。[U1]

公开高校通知确认报名截止 2026-10-10 12:00、作品截止 2026-10-15 12:00、决赛 2026-10-20；均按中国当地赛事时间理解。执行者须核对延期/变更，不沿用聊天里的倒计时。[S1]

本包不把先前聊天中未经本次完整复核的“精确评分百分比”“至少三个步骤”“必须发社媒”“4+1 分钟拆分”等当新增硬规则。工程目标仍要求真正多步 AGH 闭环；具体材料以工作组最新页面/邮件为准。

模型额度、提供的模型能力、开发 AI 使用政策、素材授权、报名状态、团队人数均不能猜测。R00 把缺口列入 `docs/HUMAN_ACTIONS.md`。不能用学生独立完成要求推导“禁止任何 AI”，也不能隐瞒 AI 参与或代签声明。

## 4. 旧代码复用策略

仅保留必要文件并记来源/提交/许可证/修改说明。仓库公开不等于无条件授权；没有可确认许可时先私有开发、记录待确认，不发布其源码。用户有权使用时亦需保留共同作者及课程资产说明。

`math-agent-research` 仅借鉴证据、冻结和复现实验方法；不需要下载其私有题库、全部模型响应或原模型接口。`caigen` 仅可借鉴幂等与执行记录思路，不迁移框架、账号、真实业务库。

## 5. 公开交付边界

发布候选包默认本地生成，公开与赛事提交需用户操作。排除 `.env`、模型凭据、AGH home、个人学生证、团队联系方式、完整私有研究材料、机器路径、缓存和未获许可资产。

对外只写验证过的能力：首版是几何仿真下的导航测试工作台。没有真实用户研究不写节省工时百分比；没有实机不写部署安全保障；没有法定认证不写通过安全认证。

AI 应把所有新事实和依赖版本增补到 `PROJECT_ROOT/docs/SOURCES.md`，注明读取日期、文件/URL、版本、实际测试证据与未验证部分。
