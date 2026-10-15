# 真实 AGH 接入

默认离线模式无需 AGH。LIVE 使用官方 Host，不是自建模型工具循环。

在仓库根目录：
```powershell
git clone https://github.com/AgnesAI-Labs/agnes-harness.git agh
git -C agh checkout --detach dc267c3c78429933e2b3d8c5d544e56bb980a574
cd agh
pnpm install --frozen-lockfile
pnpm --filter @agnes/cli build:local
```
Node ≥24.10，pnpm 10.34.5。Windows 原生构建依赖、Node headers 和初始化步骤请按 `agh/docs/guide/install.zh-CN.md` 执行；不要只复制 agnes.mjs 单文件。

通过官方界面在独立 AGH home 配置 Agnes 路由和模型。项目不提供凭据。回到 worldguard，安装 `.[api,mcp]`，复制 `configs/model_budget.example.json` 为 `configs/model_budget.local.json`，填写显式授权引用、上游 agh_root、credential_home、单运行请求/输出/时间限制。保持每运行有限预算，Key 不放该公开仓库。

```powershell
.\.venv\Scripts\python.exe scripts/probe_agh.py --config configs/model_budget.local.json
$env:WORLDGUARD_LIVE_CONFIG = (Resolve-Path configs/model_budget.local.json).Path
.\.venv\Scripts\python.exe -m worldguard.api --port 8520
```
probe 加载官方 Host 与业务 MCP，不发起模型请求。前端仍按 RUN.md 启动。缺少配置返回不可用，不静默改称 LIVE。详细机制见 `worldguard/docs/AGH_LIVE.md`；其中 8510 / Streamlit 段落为旧入口。

运行记录中的模型 ID 是配置标识，不保证不可变后端模型版本。本项目不内置 Key，不代理公开免费模型服务。
