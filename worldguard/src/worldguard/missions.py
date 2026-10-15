"""Goal presets and deterministic command assistance; not a second model runtime."""
import re
from dataclasses import asdict

from worldguard.campaign.runner import configuration
from worldguard.contracts import digest, identifier
from worldguard.evidence import read_json, write_json
from worldguard.planners.reference_astar import ReferenceAStar
from worldguard.scene import COMPLEX_FAMILIES, FAULT_KINDS, complex_layout, make_scene
from worldguard.verifier.audit import audit_path

TITLES = {"comprehensive": "场景全面检查", "blockage": "堵路恢复验证",
          "clearance": "窄通道边界测试", "recovery": "恢复策略对比"}


def generate_preview(seed, version="v1"):
    if version not in ("v1", "v2"):
        raise ValueError("INVALID_GENERATOR_VERSION")
    config_id = f"generated_{version}_s{seed}_stale"
    config = configuration(config_id)
    scene, task = make_scene(config["family"], seed)
    plan = ReferenceAStar().plan(scene, task)
    audit = audit_path(scene, task, plan.path)
    if audit["status"] != "PASS":
        raise ValueError("GENERATED_BASELINE_REJECTED")
    return {"config_id": config_id, "generator_version": f"warehouse-{version}", "seed": seed,
            "scene_hash": scene.content_hash, "scene": {**asdict(scene), "content_hash": scene.content_hash}, "task": asdict(task),
            "baseline_audit": audit, "baseline_path": list(plan.path),
            "source": "SYNTHETIC_GEOMETRIC"}


def prepare_mission(root, request):
    from worldguard.submissions import read_submission
    submission = read_submission(root, request.submission_id) if request.submission_id else None
    if submission and submission["status"] != "READY":
        raise ValueError("SUBMISSION_STATIC_ONLY")
    config_id, preset, maximum = request.config_id, request.preset, request.max_cases
    brief, notes = request.brief.strip(), []
    # Explicitly disclosed convenience parser. Unrecognized prose never becomes executable code.
    if brief:
        if any(word in brief for word in ("窄通道", "净空", "狭窄")):
            preset = "clearance"
        elif any(word in brief for word in ("优化策略", "减少转弯", "对比", "比较")):
            preset = "recovery"
        elif any(word in brief for word in ("堵路", "阻断")):
            preset = "blockage"
        match = re.search(r"(?:最多|上限|预算)\s*(\d+)\s*(?:个|例|案例)", brief)
        if match:
            desired = int(match[1])
            maximum = max(2, min(5, desired))
            if maximum != desired:
                notes.append(f"本轮支持 2–5 个案例；已将 {desired} 调整为 {maximum}，开始前可查看范围。")
        if any(word in brief for word in ("多机器人", "实机", "3D", "三维", "修改算法", "动态行人")):
            notes.append("多机器人、实机、3D、修改算法和连续动态行人不在本轮能力范围，未纳入计划。")
        notes.append("补充要求由有限关键词规则整理；完整要求随任务交给执行 Agent。结构化范围和预算优先。")
    if preset == "clearance":
        config_id = "corridor_stale"
        notes.append("窄通道测试使用专用净空走廊，包含不同通道宽度。")
    elif preset == "blockage" and FAULT_KINDS[configuration(config_id)["family"]] != "BLOCK_ROUTE":
        config_id = "fulfillment_stale"
        notes.append("已选择具有堵路注入能力的货架仓场景。")
    config = configuration(config_id)
    scene, task = make_scene(config["family"], config["seed"])
    kind = FAULT_KINDS[config["family"]]
    severities = list(range(1, 5)) if kind == "PINCH_CLEARANCE" else [1]
    if config["family"] in COMPLEX_FAMILIES:
        severities = list(range(1, len(complex_layout(config["family"], config["seed"])[-1]) + 1))
    cases = ["normal"] + [f"{kind.lower()}_{i}" for i in severities]
    selected = cases[:maximum]
    if len(cases) < maximum:
        notes.append(f"该地图提供 {len(cases)} 个不同案例，本轮按实际数量执行，不重复凑数。")
    plan = {"schema_version": "worldguard-mission/v1", "title": TITLES[preset], "preset": preset,
            "submission_id": submission["submission_id"] if submission else None,
            "navigation_strategy": submission["strategy"] if submission else None,
            "config_id": config_id, "family": config["family"], "seed": config["seed"],
            "brief": brief, "interpretation": "BOUNDED_RULES", "case_ids": selected,
            "available_cases": len(cases), "max_cases": len(selected),
            "max_actions": min(12, 2 * len(selected) + 1),
            "compare_strategies": preset == "recovery", "notes": notes,
            "scene_hash": scene.content_hash, "task_hash": task.task_hash,
            "constraints_hash": task.robot.constraints_hash,
            "steps": ["确认目标与案例范围", "执行正常基准", "注入故障并独立验收",
                      "根据失败证据恢复或停止", "比较四种候选策略" if preset == "recovery" else "汇总已验证范围",
                      "保存报告与证据"],
            "limits": ["单机器人二维几何仿真", "固定起终点、机器人尺寸和安全余量",
                       "原始失败永久保留；停止不代表到达", "未覆盖案例不计为通过"]}
    plan["mission_id"] = "mission_" + digest(plan)[:24]
    folder = root / "missions"
    folder.mkdir(parents=True, exist_ok=True)
    write_json(folder / f"{plan['mission_id']}.json", plan)
    return {**plan, "scene": {**asdict(scene), "content_hash": scene.content_hash}, "task": asdict(task)}


def read_mission(root, mission_id):
    identifier(mission_id)
    path = root / "missions" / f"{mission_id}.json"
    if not path.is_file() or path.is_symlink():
        raise ValueError("MISSION_NOT_FOUND")
    plan = read_json(path)
    body = {k: v for k, v in plan.items() if k != "mission_id"}
    if "mission_" + digest(body)[:24] != mission_id:
        raise ValueError("MISSION_CHANGED")
    return plan
