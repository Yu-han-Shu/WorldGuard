# WorldGuard

部署前二维导航故障测试工作台：选场景、运行导航器、独立检查完整路径足迹、恢复/停止、导出可重放证据。

**React 工作台、HTTP API 与真实 Agnes/AGH 核心闭环已有实跑证据。** 支持独立审计、恢复/停止及报告 / ZIP；E2 公平对照、当前发布包最终验收与参赛材料仍待完成。当前启动入口见 [RUN.md](RUN.md)，提交口径见 [最新规则](docs/SUBMISSION_RULES_CURRENT.md)。
仅合成几何场景；无真机、动力学或安全认证。详见 docs/STATE.md、docs/RELEASE_READINESS.md。

## 独立前端开发

已提供 HTTP API、交互式接口文档、TypeScript 客户端及生成类型。
从 [前端接入指南](frontend/README.md) 开始，完整约定见 [前端交接](docs/FRONTEND_HANDOFF.md)。
前端后端联调不需要 AGH、Streamlit 或模型密钥。

```powershell
python -m pip install -e ".[api]"
python -m worldguard.api
```

打开 http://127.0.0.1:8520/docs 可直接测试接口；原 Streamlit 界面仍使用 8510 端口。

## 旧版 Streamlit 启动（历史入口，当前 React 见 RUN.md）

双击 `start-worldguard.cmd`，然后打开 http://127.0.0.1:8510 。
也可在项目目录运行：

```powershell
.\.venv\Scripts\python.exe scripts\launch.py
```

启动器会复用本机 8520 API，或自动启动离线 API。工作台现在通过 HTTP API 运行。
本机已有授权模型配置时，启动 `scripts/launch.py --live-config configs/model_budget.local.json`；
若已有 API 尚未启用 LIVE，请先停止该 API 再使用此命令。不会改写或重置已有请求额度。
选择双通道绕行/单入口目标区，保留“陈旧视图”，点击“开始 LIVE Agnes 测试”调用模型，
或点击“开始离线测试”使用规则流程。按钮是否可用取决于后端 capabilities。
可切换案例查看原始 FAIL 和恢复 PASS；停止不会计入到达。ZIP 包含原始输入、结果、事件与报告。
后台任务串行执行；当前规划动作结束后取消会阻止下一动作。刷新不会发起新测试。

## 历史离线包安装记录（当前候选需重新验证）

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-build-isolation --no-deps -e .
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\launch.py
```

锁文件是本机 Windows 环境的实际版本；包含 pywin32。POSIX 启动脚本已提供，但 POSIX 安装/运行未测，不能直接套用此平台锁。
最低语法目标 Python 3.11；3.11 本身未实测。二维核心无第三方依赖，UI 使用 Streamlit，工具服务使用官方 MCP SDK。

## 命令行复现

```powershell
.\.venv\Scripts\python.exe scripts\doctor.py
.\.venv\Scripts\python.exe -m worldguard.cli demo --out artifacts/demo
.\.venv\Scripts\python.exe -m worldguard.cli plan --scene dual_route --out artifacts/plan
.\.venv\Scripts\python.exe scripts\summarize_evaluation.py --verify
```

demo 会打印每个实际 case-dir。将其填入下面命令，输出目录必须不存在：

```powershell
.\.venv\Scripts\python.exe -m worldguard.cli replay --case-dir CASE_DIRECTORY --out artifacts/replayed_case
```

CLI 退出码：0 成功；2 非法输入/环境错误；3 无规划路径；4 重放不一致。
重放标为 REPLAY，不会调用模型。输入哈希不一致即拒绝。原结果不覆盖。

## AGH / Agnes 接入状态

官方 checkout 固定为 `dc267c3c78429933e2b3d8c5d544e56bb980a574`，不放入发布包。
本地配置 `configs/local.json` 与 `.local/agh-home` 均排除打包；profile 使用官方内置 `local-dev`，通过独立 home 与日常账户隔离。
MCP 本地协议测试：`python scripts/mcp_smoke.py`。服务入口：`python -m worldguard.mcp_server`。
AGH 用经过核对的 `mcp add/trust/enable/tools` 接入；当前执行结果见 docs/AGH_TRACE_MAPPING.md。
受限 LIVE 使用生产官方 Host、官方模型与 MCP 适配器；三类故障真实验收见 `evidence/batches/AGH_LIVE/`。
安装 `.[api,mcp]` 并配置本机有限授权后，可通过 HTTP API 和 Streamlit 工作台运行；完整说明见 [AGH_LIVE](docs/AGH_LIVE.md)。
默认模型调用关闭，前端和仓库无需 Key；预算、启动参数与 AGH home 不入库。

## 评测、来源与材料

`experiments/final_v1` 保存运行前冻结的协议、源文件清单、12 个新案例的双方法原始结果及失败重放。
`docs/EVALUATION.md` 给出实际计数。TEST_MUTANT 为显式测试夹具，不是旧导航仓库真实缺陷。
旧代码未复制；共同作者、参赛资格、开发 AI 政策与视频由用户确认。
本地打包不自动上传、发布或向赛事提交。
