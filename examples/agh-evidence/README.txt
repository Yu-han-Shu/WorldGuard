运行证据：四项要求对应表

1. AGH 执行记录：两个 run_ 子文件夹中的 agh_session.jsonl 与 agh_summary.json。
   记录来自官方 AGH Host 实际执行事件，保留序号、时间、工具 ID、输入、输出与模型标识；是脱敏投影，并非模型撰写的轨迹描述，也不标称官方网页原生导出文件。
2. 工具调用链：核心工具调用链.json。从复杂仓库 block_route_2 提取运行、原始验收、恢复和恢复后验收，调用/结果序号分别为 216/224、239/243、256/260、273/277；toolUseId 一一对应。
3. Agnes 核心参与：上述调用前 request/sent 事件记录 account-agnes-cn-hackathon / agnes-3.0-flash；模型在 AGH 中发起导航测试、读取验收反馈并调用恢复工具。原始事件可独立定位，不以 UI 标签代替证据。
4. 配置与专业验证：关键配置.json、各运行 report.json、05 三类样例的 task/audit/result/manifest，以及 replay-results。
   原始堵路路径净空 -0.230 m / FAIL；恢复后 0.145 m / PASS。圆形机器人半径 0.18 m，安全余量 0.05 m，原始约束保持一致。

原始文件未改写，投影文件 SHA-256 与 agh_summary 匹配。manifest 哈希针对规范化 JSON；交付包 SHA256SUMS.json 针对文件字节。两种哈希的用途不同。
模型请求数为运行级计数；完整 token/费用未知，保留 null。运行时间与序号在原记录中；本次整理不产生新的模型运行。
