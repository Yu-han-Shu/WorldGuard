"""Shared budgets and business API. Adaptive rule uses only observed audit outcomes."""

import random


def select_case(method, remaining, observed, rng):
    if method == "SeededRandom":
        return rng.choice(remaining)
    if method == "AdaptiveRule":
        pinch = [c for c in remaining if c["fault"] == "PINCH_CLEARANCE"]
        if pinch:
            history = [(c["severity"], status) for c, status in observed if c["fault"] == "PINCH_CLEARANCE"]
            failed = [severity for severity, status in history if status == "FAIL"]
            passed = [severity for severity, status in history if status == "PASS"]
            lower, upper = max(failed, default=0), min(passed, default=5)
            pivot = (lower + upper) / 2
            return min(pinch, key=lambda c: (abs(c["severity"] - pivot), c["severity"]))
        risks = [c for c in remaining if c["fault"] != "NONE"]
        if risks:
            return risks[0]
    if method not in ("FixedCoverage", "AdaptiveRule"):
        raise ValueError("UNKNOWN_BASELINE")
    return remaining[0]


def execute(runner, run_id, method="FixedCoverage", seed=101):
    rng = random.Random(seed)
    remaining = runner.list_candidates(run_id)
    mission = runner._get(run_id).get("mission")
    if mission:
        runner.publish_decision(run_id, "PLAN", "先检查正常基准，再按测试范围执行故障案例；失败后依据独立审计恢复或停止。",
                                "", [], [c["case_id"] for c in remaining])
    observed = []
    sequence = 0
    while remaining:
        case = next((c for c in remaining if c["fault"] == "NONE"), None) if mission else None
        case = case or select_case(method, remaining, observed, rng)
        remaining.remove(case)
        cid = case["case_id"]
        try:
            plan = runner.run_case(run_id, cid, f"run_{sequence}")
            audit = runner.audit_path(run_id, cid, plan["path_id"])
            status = audit["audit"]["status"]
            observed.append((case, status))
            if status != "PASS":
                if mission:
                    runner.publish_decision(run_id, "RECOVERY", "原始路线未通过独立验收，保留失败证据，更新地图后重新规划并复验。",
                                            cid, [audit["evidence_id"]], [])
                plan = runner.recover_case(
                    run_id, cid, "REFRESH_MAP_REPLAN", [audit["evidence_id"]], f"recover_{sequence}"
                )
                audit = runner.audit_path(run_id, cid, plan["path_id"])
                if audit["audit"]["status"] != "PASS":
                    runner.recover_case(run_id, cid, "SAFE_STOP", [audit["evidence_id"]], f"stop_{sequence}")
        except ValueError as error:
            if str(error) not in (
                "SUT_BUDGET_EXHAUSTED",
                "WALL_TIME_BUDGET_EXHAUSTED",
                "CAMPAIGN_NOT_RUNNING",
            ):
                raise
            break
        sequence += 1
    if mission and mission["compare_strategies"] and runner._get(run_id)["status"] == "RUNNING":
        run = runner._get(run_id)
        target = next((a for a in reversed(list(run["audits"].values())) if a["case_id"] != "normal"), None)
        if target:
            runner.optimize_case(run_id, target["case_id"], target["evidence_id"], "mission_compare")
    return runner.finish_campaign(run_id)
