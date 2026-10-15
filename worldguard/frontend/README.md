# 前端从这里开始

导航优化新增 `optimizeCase(runId, caseId)` 与 `optimization(runId, caseId)`，返回强类型候选、独立审计和长度/转弯/净空/评分；按 capabilities.features.strategy_optimization 展示入口。详情见交接文档。

2026-10-13 后续更新：真实 Agnes 已接到相同接口，后端配置和验收见 [AGH_LIVE](../docs/AGH_LIVE.md)。
前端按 capabilities 控制 LIVE 入口，默认离线使用不受影响；TypeScript 契约已增加 AgnesAGH、会话证据和用量完整性字段。

当前目录已含 React / Vite 应用。完整启动见 [RUN.md](../RUN.md)：API 默认 8520，前端 5173；执行 npm ci 后 npm run dev。下文保留 SDK 接入说明，前端本身不持有模型 Key。

## 1. 拉代码并启动后端

```powershell
git clone -b codex/worldguard-execution https://github.com/Yu-han-Shu/agnes-hackathon.git
cd agnes-hackathon/worldguard
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[api]"
.\.venv\Scripts\python.exe -m worldguard.api
```

Windows 实测 Python 3.13。Python 3.11+ 为支持目标，其他环境未实测。
后端地址 `http://127.0.0.1:8520`，交互文档 `/docs`，机器接口契约 `/openapi.json`。
前端开发不必安装 Streamlit、MCP 或运行时 `agh/`。
已有项目虚拟环境可以直接运行最后一条启动命令。

## 2. 接入前端项目

复制 `client.ts`、`schema.d.ts` 到前端源码目录；类型直接从后端 OpenAPI 生成。
如使用 Next.js，从客户端组件调用；浏览器中的地址指向使用者本机。
`example.ts` 提供启动和轮询示例。所有接口详见 [交接文档](../docs/FRONTEND_HANDOFF.md)。

```ts
import { createWorldGuardClient } from './client';

const api = createWorldGuardClient('http://127.0.0.1:8520');
const run = await api.createRun({
  config_id: 'dual_route_stale',
  request_id: crypto.randomUUID(),
  execution_mode: 'automatic',
  tester: 'AdaptiveRule',
});
const runId = run.state.run_id;
// 将 runId 保存到 URL 或 localStorage；刷新页面只 GET，不重复 POST。
const current = await api.getRun(runId);
const candidates = await api.candidates(runId);
const caseData = await api.getCase(runId, 'block_route_1');
// <img src={api.mapURL(runId, 'block_route_1')} />
// 完成后 <a href={api.exportURL(runId)}>下载证据</a>
```

创建请求的 `request_id` 在点击时生成一次；网络重试复用同一个 ID。
默认允许来自 localhost/127.0.0.1 的 3000、5173、8080 端口跨域访问。
其他端口启动后端前设置 `WORLDGUARD_CORS_ORIGINS`，逗号分隔完整 origin。

## 3. 更新类型和验证

```powershell
# worldguard 目录
.\.venv\Scripts\python.exe scripts/export_openapi.py
cd frontend
npm ci
npm run generate
npm run typecheck
# 已启动后端时，实际发送 HTTP 请求验证客户端
$env:WORLDGUARD_API_URL = 'http://127.0.0.1:8520'
npm test
```

`npm test` 没设置地址时会显示 SKIP，不能当作后端联调通过。

## 当前可用与预留

- 可用：自动/手动测试、3 种测试员、3 类故障、地图 JSON/SVG、原始/恢复路径、独立审计、取消、事件轮询、历史记录、报告和 ZIP。
- LIVE_AGNES 已实现；未配置真实模型的默认 API 仍返回 `503 LIVE_NOT_AVAILABLE`，以 capabilities 为准。旧导航器、SSE、重启后续跑不作已开放承诺。
- 后端没有账户/租户系统，启动器只监听本机；本轮供各开发者本机联调。远程部署需要另行配置访问控制。
- 真实密钥不进前端，不需要放到仓库。`.env.example` 只给非敏感配置名称。
