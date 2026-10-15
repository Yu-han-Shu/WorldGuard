# 三类代表样例

全部为 2026-10-15 已保存的 Agnes LIVE 运行案例，不是新模型实验。

| 目录 | 内容 | 预期 / 实际 |
| --- | --- | --- |
| 01-normal | 复杂仓库正常基线 | 原始通过，到达 |
| 02-boundary | pinch_clearance_2 | 足迹不满足净空，恢复未获合格路径，停止 |
| 03-failure-recovery | block_route_2 | 原始失败保留，恢复路径独立通过 |

从仓库根目录运行（先安装 worldguard）：
```powershell
python -m worldguard.cli replay --case-dir examples/03-failure-recovery --out artifacts/replay-failure-new
```
每次使用不存在的新输出目录。三份原始样例的 manifest 已核对，发布时重放结果见 replay-results。重放依据原策略参数重新规划与验收，不调用模型。

注意：manifest 是规范化 JSON 内容哈希。部分旧 report.md 模板未正确显示运行级模型字段，以 result.json 的 LIVE_AGNES 和提交报告中的模型登记为准；case 层 null 不是零请求。原始文件未为发布修改。
