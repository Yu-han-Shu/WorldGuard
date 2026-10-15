"""Archive a batch assessment. Status is supplied by the executor, never inferred from prose."""

import argparse
import datetime
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("batch")
parser.add_argument("status")
parser.add_argument("summary")
parser.add_argument("next")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
folder = root / "artifacts/batches" / args.batch
folder.mkdir(parents=True, exist_ok=True)
state_path = root / "artifacts/batches/status.json"
state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
stamp = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
state[args.batch] = {"status": args.status, "summary": args.summary, "timestamp": stamp}
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
records = folder / "commands.jsonl"
commands = (
    [json.loads(line) for line in records.read_text(encoding="utf-8").splitlines()]
    if records.exists()
    else []
)
table = "\n".join(f"| `{' '.join(r['command'])}` | {r['exit_code']} | {r['output']} |" for r in commands)
handoff = f"""# {args.batch} 交接

- 时间：{stamp}
- 状态：{args.status}；仅针对下述范围。
- 工作分支：codex/worldguard-execution；本地未提交，源包及上游只读。
- 实际交付与缺口：{args.summary}
- 本批改动：以源文件清单和本批 evidence 为准，未运行的能力不计通过。

## 实际命令（工作目录 PROJECT_ROOT）

| 命令 | 退出码 | 原始输出 |
|---|---|---|
{table}

## 授权与证据

外部模型调用 0；tokens/费用未测，LIVE_AGNES=NOT_RUN。只使用 DETERMINISTIC / 协议离线测试。
风险：LIVE 预算、项目专用账号配置与运行期工具隔离尚未验收；见 HUMAN_ACTIONS.md。
接口按冻结规范；限制和实现取舍见 DECISIONS.md。本批不修改原始历史结果。

## 下一入口

{args.next}。先读 AGENTS.md、STATE.md、本交接及相应规范。不要重建已通过模块。
"""
(folder / "HANDOFF.md").write_text(handoff, encoding="utf-8")
(root / "docs/HANDOFF.md").write_text(handoff, encoding="utf-8")
rows = "\n".join(
    f"| R{i:02} | {state.get(f'R{i:02}', {}).get('status', 'NOT_STARTED')} | artifacts/batches/R{i:02}/ | {state.get(f'R{i:02}', {}).get('summary', '尚未执行')} |"
    for i in range(9)
)
(root / "docs/STATE.md").write_text(
    f"""# WorldGuard 当前状态

更新时间：{stamp}；分支 codex/worldguard-execution；未推送。
PACK_ROOT / PROJECT_ROOT / AGH_ROOT 的绝对路径仅在 gitignored configs/local.json。
已测 Windows / PowerShell / Python 3.13.12；依赖实际版本见 requirements.lock 与 doctor 输出。

| 批次 | 状态 | 证据 | 范围/缺口 |
|---|---|---|---|
{rows}

## 独立门槛与授权

各批验收不得替代 LIVE：真实 Agnes 调用、业务 Agent 闭环、Agent 增量评测均 NOT_RUN。
external_model_calls_allowed=false；批准预算未提供；密钥值未读取；模型路由未独立核实。
开发 AI 使用政策、成员声明、视频与赛事材料 HUMAN_PENDING。
product_ready=false；live_evidence_ready=false；competition_ready=false。
下一入口：{args.next}。已知问题见 HANDOFF.md、HUMAN_ACTIONS.md。
""",
    encoding="utf-8",
)
with (root / "docs/DECISIONS.md").open("a", encoding="utf-8") as stream:
    stream.write(f"\n- {stamp} {args.batch}：{args.status}。{args.summary}\n")
print(f"{args.batch}: {args.status}; archived {len(commands)} command records")
