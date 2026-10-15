import argparse
from pathlib import Path

from worldguard.evidence import read_json, write_json


def summarize(folder):
    records = read_json(folder / "results/raw.json")
    groups = {}
    for row in records:
        result = read_json(folder / row["case_directory"] / "result.json")
        oracle = row["oracle"]["status"]
        group = groups.setdefault(
            row["method"],
            {
                "cases": 0,
                "original_failures": 0,
                "original_unknown": 0,
                "reached": 0,
                "safe_stop": 0,
                "oracle_reachable": 0,
                "oracle_unreachable": 0,
                "oracle_unknown": 0,
                "reachable_reached": 0,
                "correct_stop": 0,
                "false_stop": 0,
                "sut_executions": 0,
                "replays": 0,
                "replay_matches": 0,
                "model_requests": 0,
            },
        )
        group["cases"] += 1
        group["original_failures"] += result["original_audit"]["status"] == "FAIL"
        group["original_unknown"] += result["original_audit"]["status"] == "UNKNOWN"
        group["reached"] += result["reached"]
        stopped = result["navigation_status"] == "SAFE_STOP"
        group["safe_stop"] += stopped
        group["oracle_reachable"] += oracle == "REACHABLE"
        group["oracle_unreachable"] += oracle == "UNREACHABLE"
        group["oracle_unknown"] += oracle == "UNKNOWN"
        group["reachable_reached"] += oracle == "REACHABLE" and result["reached"]
        group["correct_stop"] += oracle == "UNREACHABLE" and stopped
        group["false_stop"] += oracle == "REACHABLE" and stopped
        group["sut_executions"] += result["sut_executions"]
        if row["replay_path"] is not None:
            replay = read_json(folder / row["replay_path"])
            group["replays"] += 1
            group["replay_matches"] += replay["matches"]
    for group in groups.values():
        for name, numerator, denominator in (
            ("reachable_reached_rate", "reachable_reached", "oracle_reachable"),
            ("correct_stop_rate", "correct_stop", "oracle_unreachable"),
            ("false_stop_rate", "false_stop", "oracle_reachable"),
            ("reproduction_rate", "replay_matches", "replays"),
        ):
            group[name] = group[numerator] / group[denominator] if group[denominator] else None
        group["danger_detection_rate"] = None
        group["safe_path_false_positive_rate"] = None
        group["unmeasured_reason"] = (
            "No independent labeled candidate-path dataset; do not use verifier as its own truth"
        )
    return {
        "experiment": folder.name,
        "E1": groups,
        "E2": "NOT_RUN",
        "AgnesAGH": "NOT_RUN",
        "legacy_adapter": "BLOCKED_SOURCE_PERMISSION",
        "model_tokens": None,
        "model_cost": None,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", type=Path, default=Path("experiments/final_v1"))
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    summary = summarize(args.experiment)
    if args.verify:
        if summary != read_json(args.experiment / "results/summary.json"):
            raise SystemExit("SUMMARY_MISMATCH")
        print("RAW_RECOMPUTATION_MATCH")
    else:
        write_json(args.experiment / "results/summary.json", summary)
        print(summary)
