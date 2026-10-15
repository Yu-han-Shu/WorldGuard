import argparse
import json
from dataclasses import asdict
from pathlib import Path

from worldguard import __version__


def main():
    parser = argparse.ArgumentParser(description="WorldGuard — bounded 2D navigation tests")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command")
    plan = commands.add_parser("plan")
    plan.add_argument("--scene", choices=["dual_route", "corridor", "single_entry"], required=True)
    plan.add_argument(
        "--planner", choices=["reference_safe_astar", "legacy_adapter"], default="reference_safe_astar"
    )
    plan.add_argument("--seed", type=int, default=11)
    plan.add_argument("--block-goal", action="store_true", help="Synthetic blocked-goal acceptance fixture")
    plan.add_argument("--out", type=Path, required=True)
    demo = commands.add_parser("demo")
    demo.add_argument("--out", type=Path, default=Path("artifacts/runs"))
    demo.add_argument("--seed", type=int, default=11)
    replay = commands.add_parser("replay")
    replay.add_argument("--case-dir", type=Path, required=True)
    replay.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    from worldguard.evidence import replay_case, run_case, write_json
    from worldguard.faults import CaseSpec
    from worldguard.planners.reference_astar import ReferenceAStar
    from worldguard.scene import make_scene

    try:
        if args.command == "plan":
            scene, task = make_scene(args.scene, args.seed)
            if args.block_goal:
                from dataclasses import replace

                scene = replace(scene, occupied=(*scene.occupied, scene.world_to_cell(task.goal_xy_m)))
            if args.planner == "legacy_adapter":
                raise RuntimeError("LEGACY_BLOCKED: source/license not verified")
            result = ReferenceAStar().plan(scene, task)
            args.out.mkdir(parents=True, exist_ok=False)
            write_json(
                args.out / "plan.json",
                {
                    "scene": asdict(scene),
                    "task": asdict(task),
                    "plan": asdict(result),
                    "path_hash": result.path_hash,
                    "runtime_mode": "DETERMINISTIC",
                    "audit": "NOT_RUN",
                },
            )
            print(json.dumps({"code": result.code, "path_hash": result.path_hash}))
            return 0 if result.code == "PLANNED" else 3
        if args.command == "demo":
            for family, kind in (
                ("dual_route", "NONE"),
                ("dual_route", "BLOCK_ROUTE"),
                ("single_entry", "DISCONNECT_GOAL"),
                ("corridor", "PINCH_CLEARANCE"),
            ):
                scene, task = make_scene(family, args.seed)
                case = CaseSpec(kind.lower(), scene.content_hash, kind, args.seed)
                result, case_dir = run_case(scene, task, case, args.out)
                print(
                    json.dumps(
                        {
                            "run_id": result["run_id"],
                            "case_dir": str(case_dir),
                            "navigation": result["navigation_status"],
                            "audit": result["original_audit"]["status"],
                        }
                    )
                )
            return 0
        if args.command == "replay":
            result = replay_case(args.case_dir, args.out)
            print(json.dumps(result, ensure_ascii=False))
            return 0 if result["matches"] else 4
        parser.print_help()
        return 0
    except (ValueError, RuntimeError, OSError) as error:
        print(json.dumps({"execution_status": "ERROR", "error": str(error)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
