# 来源与证据边界

核对日期：2026-10-12（Asia/Shanghai）。

| 来源 | 版本 | 使用与状态 |
|---|---|---|
| WorldGuard_Execution_Pack | 1.0 | 本项目冻结规范，原包只读 |
| https://github.com/AgnesAI-Labs/agnes-harness | dc267c3c78429933e2b3d8c5d544e56bb980a574 | 本地只读 checkout，工作树干净；CLI 验证另列 |
| https://github.com/Yu-han-Shu/realityscan-uv3d-navigation | 802e179ab899e0cec11dcaee2b7c722c733613b4（包中参考） | 未在工作区找到；网页读取失败；未复制、未实测；许可证待确认 |
| https://github.com/modelcontextprotocol/python-sdk | 以 requirements.lock 实际安装版本为准 | 官方 SDK，用于本地 stdio；不是模型 API |

源包的旧代码静态发现与历史成绩均不属于本项目实测。赛事期限、规则、报名情况和开发 AI 政策尚未独立确认；不作已合规声明。

2026-10-13 本机核对并实际使用同一固定 AGH checkout 的 `packages/host/src/host.ts`、`assemble/provider.ts`、`configuration.ts`、`session-title.ts`、`packages/base/src/mcp/connect.ts` / `register.ts`、协议 preset/hook validators 与 official session.scan。
实际官方 Host 插件加载、MCP 工具调用和 Agnes route/model 请求证据见 evidence/batches/AGH_LIVE。
使用已配置国内站 `https://api.agnes-ai.cn/v1` 的 `agnes-3.0-flash`；费用未知，不由免费额度说法推算 0。
新增 API 仍是本机单进程，未进行 POSIX、实机、赛事材料或独立第三方验收。
