# WorldGuard 运行指南

更新：2026-10-15。当前展示入口是 React 工作台，默认前端 5173 / API 8520。以下为代码核对后的启动步骤；最终提交包的新目录安装仍待本轮验收，不沿用旧 Streamlit 包结论。

## Windows 本地启动

需要 Python、Node.js/npm；本机有 Windows / Python 3.13 与 Node 24 的实跑证据。进入 `worldguard` 目录，在终端一执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[api,mcp]"
.\.venv\Scripts\python.exe -m worldguard.api --port 8520
```

终端二进入 `worldguard/frontend`：

```powershell
npm ci
$env:VITE_WORLDGUARD_API_URL = 'http://127.0.0.1:8520'
npm run dev -- --port 5173 --strictPort
```

打开 http://127.0.0.1:5173/#agent 。输入目标、添加受限 JSON 策略或载入示例，准备并确认测试计划，再执行和查看报告。

## 真实模型

按 docs/AGH_LIVE.md 准备官方 AGH 与有界本机配置。启动 API 前设置：

```powershell
$env:WORLDGUARD_LIVE_CONFIG = (Resolve-Path configs/model_budget.local.json).Path
.\.venv\Scripts\python.exe -m worldguard.api --port 8520
```

本机配置应明确 provider、请求预算和超时；以实际 summary 的 model / route 为准，不按界面名称猜模型。配置与 Key 不入库、不放前端。默认 API 不启动真实模型。已有端口占用时使用另一对端口，不直接结束用户服务。

## 离线复现

```powershell
.\.venv\Scripts\python.exe -m worldguard.cli demo --out artifacts/demo-new
.\.venv\Scripts\python.exe -m worldguard.cli replay --case-dir CASE_DIRECTORY --out NEW_OUTPUT_DIRECTORY
```

重放输出目录必须不存在；重放不调用模型，不重新证明模型决策。三类提交样例含原始输入、路径、审计和 manifest。

## 旧入口

`scripts/launch.py`、`start-worldguard*.cmd` 和 8510 端口属于旧 Streamlit 工作台，不能替代上面的 React 启动说明。
范围：单机器人二维几何仿真；SAFE_STOP 不算到达；恢复通过不覆盖原始失败。任意 Python 上传不作为可执行导航程序。
