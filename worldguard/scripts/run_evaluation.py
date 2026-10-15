"""Freeze before execution. E1 only; no artificial Agnes comparison without LIVE."""

import argparse
import datetime
import hashlib
import sys
from pathlib import Path

from summarize_evaluation import summarize

from worldguard.contracts import digest
from worldguard.evidence import replay_case, run_case, write_json
from worldguard.faults import CaseSpec, inject
from worldguard.scene import DEV_SEEDS, make_scene
from worldguard.verifier.oracle import reachable


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", default="final_v1")
    args = parser.parse_args()
    from worldguard.contracts import identifier

    identifier(args.experiment)
    root = Path(__file__).resolve().parents[1]
    target = root / "experiments" / args.experiment
    target.mkdir(parents=True, exist_ok=False)
    (target / "results").mkdir()
    versions = {}
    for name in ("src", "tests", "scripts", "prompts", "scenarios"):
        for path in sorted((root / name).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                versions[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ("app.py", "pyproject.toml", "requirements.lock"):
        versions[name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    protocol = {
        "experiment": args.experiment,
        "frozen_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "source_manifest_hash": digest(versions),
        "runtime_mode": "DETERMINISTIC",
        "E1_cases": 12,
        "methods": ["reference_current", "TEST_MUTANT_stale_view"],
        "legacy": "BLOCKED",
        "E2": "NOT_RUN_NO_LIVE_AGH",
        "model_requests": 0,
        "seed_rule": "1001+i,2001+i,3001+i,4001+i for i=0..2 after freezing",
        "development_seeds": list(DEV_SEEDS),
        "max_sut_per_case": 2,
        "oracle": "independent continuous geometry on finite 4-neighbor graph; timeout=15s gives UNKNOWN",
        "failure_signature": "planner_version + violation code + family + obstacle/boundary class",
        "timeouts": "retain; UNKNOWN; do not count as SUT defects",
        "comparison_scope": "E1 correctness/recovery only; no Agent advantage claims",
        "danger_detection_rate": "null: independent candidate-path truth set not constructed",
        "data_isolation": "no model executed; no blind E2 claim",
    }
    write_json(target / "versions.json", versions)
    write_json(target / "protocol.json", protocol)
    (target / "protocol.sha256").write_text(digest(protocol) + "\n", encoding="utf-8")
    (target / "protocol.md").write_text(
        "# Frozen E1 protocol\n\n12 new cases, two paired SUT views. All inputs and source versions frozen before execution. "
        "Four groups: normal, recoverable block, clearance boundary, disconnected goal. "
        "TEST_MUTANT deliberately uses stale maps and is not a legacy defect. E2 / Agnes NOT_RUN. "
        "No threshold/seed selection after seeing results. See protocol.json for counts and failure policy.\n",
        encoding="utf-8",
    )
    sys.path.insert(0, str(root / "tests"))
    from evaluation_mutants import METHODS

    records, errors, signatures = [], [], {method: set() for method in METHODS}
    for group, family, kind, base in (
        ("normal", "dual_route", "NONE", 1001),
        ("block", "dual_route", "BLOCK_ROUTE", 2001),
        ("clearance", "corridor", "PINCH_CLEARANCE", 3001),
        ("stop", "single_entry", "DISCONNECT_GOAL", 4001),
    ):
        for variant in range(3):
            seed = base + variant
            assert seed not in DEV_SEEDS
            scene, task = make_scene(family, seed)
            severity = (1, 2, 4)[variant] if group == "clearance" else 1
            case = CaseSpec(f"{group}_{seed}", scene.content_hash, kind, seed, severity)
            oracle = reachable(inject(scene, case), task)
            for method, stale in METHODS.items():
                try:
                    result, case_dir = run_case(scene, task, case, target / "runs" / method, stale_view=stale)
                    replay_path = None
                    if result["original_audit"]["status"] == "FAIL":
                        replay_dir = target / "reproduction" / method / case.case_id
                        replay_case(case_dir, replay_dir)
                        replay_path = (replay_dir / "replay.json").relative_to(target).as_posix()
                        for violation in result["original_audit"]["violations"]:
                            signatures[method].add(
                                (
                                    result["original_plan"]["planner_version"],
                                    violation["code"],
                                    family,
                                    violation.get("kind"),
                                )
                            )
                    records.append(
                        {
                            "method": method,
                            "seed": seed,
                            "group": group,
                            "oracle": oracle,
                            "case_directory": case_dir.relative_to(target).as_posix(),
                            "replay_path": replay_path,
                        }
                    )
                except (ValueError, OSError, RuntimeError) as error:
                    errors.append({"method": method, "seed": seed, "error": type(error).__name__})
                    raise
                finally:
                    write_json(target / "results/raw.json", records)
                    write_json(target / "errors.json", errors)
    write_json(target / "unique_failure_signatures.json", {k: sorted(v) for k, v in signatures.items()})
    write_json(target / "model_usage.json", {"requests": 0, "tokens": None, "cost": None, "E2": "NOT_RUN"})
    summary = summarize(target)
    write_json(target / "results/summary.json", summary)
    print(summary)
    rows = "\n".join(
        f"| {method} | {v['cases']} | {v['original_failures']} | {v['original_unknown']} | {v['reached']} | {v['safe_stop']} | {v['replay_matches']}/{v['replays']} |"
        for method, v in summary["E1"].items()
    )
    (root / "docs/EVALUATION.md").write_text(
        f"""# {args.experiment} 实测结果

来源：experiments/{args.experiment}/results/raw.json；逐例结果、oracle、哈希、重放均保留。
协议在运行前冻结，见 protocol.json / protocol.sha256 / versions.json。

| 方法 | 案例 | 原始 FAIL | 原始 UNKNOWN | 恢复后到达 | SAFE_STOP | 失败重放一致 |
|---|---|---|---|---|---|---|
{rows}

上述两个方法在相同 12 个最终案例上成对执行；UNKNOWN 空路径并未计为错误放行。
正确停止仅按独立有限网格 oracle 判定，不能推广为任意连续轨迹无路。
TEST_MUTANT_stale_view 是显式测试夹具，不是旧仓库已证实漏洞。
危险检出率/误报率留 null：没有独立标注的候选路径真值数据集，避免验收器给自己打分。
E2、AgnesAGH=NOT_RUN，旧导航适配器=BLOCKED；不能宣称 Agent 优于固定/随机/规则，也没有人工工时节省数据。
模型调用 0；tokens/费用 null。小样本只支持本范围内的描述性结果。
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
