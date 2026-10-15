# AGH 与产品事件对应

## 2026-10-13 实际 LIVE 更新

真实官方 Host 会话与产品 run_id 已关联，完成 nonce 回环、故障恢复/停止与多案例流程。
官方 `session.scan` 原始 seq/type 投影保存到 `agh_session.jsonl`；只保留请求的 route/model、工具调用与工具结果，删除其他事件 payload（包括模型私有推理/提示词）。
`ledger_sha256` 是该脱敏投影的精确 UTF-8 字节哈希，不冒充上游完整数据库的 hash-chain 认证。
`agh_summary.json` 保存模型身份、会话引用、nonce 核对及 `product_event_links`。
业务动作通过 run_id、case_id 和输入/输出哈希与 CampaignRunner 独立事件匹配；不匹配则拒绝通过。
health、绑定已有 campaign、请求 finish 是输送层事实；最后实际封存报告由 Host 完成后执行。
请求总数来自包住官方 Provider 的全局计数，包括辅助请求；仅凭 request/sent 的条数不能推出总数。
外部导入的轨迹仍为 UNVERIFIED_IMPORT，不能通过修改文件内容自动提升为 LIVE。
接口与复现入口见 [AGH_LIVE](AGH_LIVE.md)，本轮证据见 evidence/batches/AGH_LIVE。
以下内容保留 R01 初期控制面验收的历史范围。

当前状态：MCP_PROTOCOL_PASS；AGH CLI 帮助已验证；官方 host 连接 ready、工具目录 wg_health 已实测；业务 LIVE 轨迹 NOT_RUN。
MCP SDK 2.3.0；实现基于本机安装 API 检查，使用 MCPServer / Client / StdioServerParameters。

产品事件包含 run_id / case_id / tool_name / request_id / 输入输出哈希 / runtime_mode。
原始结果保存在每个 run 的 evidence 目录；事件不保存提示词、密钥或私有思维链。
每个 MCP 进程仅能引用自己签发的 run_id；不接受文件路径、URL、代码。

尚缺：官方 AGH 会话级只允许 wg_* 的验证、路由身份、可执行模型请求/输出预算、真实会话关联与 tokens 用量。
当前所有业务工具只标 DETERMINISTIC，不能用手写会话 ID 将它们提升为 LIVE。
LIVE 按钮因此保持不可用，agh_bridge.run_live 明确报错；不是完整可调用的 LIVE 桥接实现。

后续在批准预算和隔离完成后，为每个 run 保存 AGH 原始会话引用和逐调用关联表，再进行 R01/R04 验收。

## 本轮实际控制面接入

使用独立 `.local/agh-home` 与官方内置 profile `local-dev`，未读取或迁移日常账户密钥。
初次自定义 profile `worldguard-dev` 缺少内置模板；改用独立 home + local-dev 后解决。
CLI 变更要求交互终端，非交互调用取消；通过正常 TTY 审核创建、trust、enable 后成功，没有关闭沙箱或修改上游。
服务器 `worldguard` 只允许 `wg_health`，不是对业务工具或任意 shell 的授权。
`mcp status worldguard`：connection=ready，tools=1；`mcp tools worldguard` 返回 wg_health。
配置 revision：c7666d9e687535fc7e2ade2892c1e8cf8c802ad3ab6e1c9739c25cb067f0b2ba。
这些是 CONTROL_PLANE/CATALOG 证据；不能等价为 AGH 会话执行或 LIVE_AGNES_PASS。
验收结束已停止此独立 daemon，保留配置；未停止或修改用户原本的日常 AGH 实例。
