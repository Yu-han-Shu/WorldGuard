"""Export real deterministic map geometry for the frontend's read-only scene library."""
import json
from dataclasses import asdict
from pathlib import Path

from worldguard.campaign.runner import CONFIGS
from worldguard.scene import make_scene


def main():
    previews = {}
    for config in CONFIGS.values():
        key = f"{config['family']}_{config['seed']}"
        if key in previews:
            continue
        scene, task = make_scene(config["family"], config["seed"])
        previews[key] = {"scene": {**asdict(scene), "content_hash": scene.content_hash},
                         "task": asdict(task)}
    target = Path(__file__).resolve().parents[1] / "frontend/src/data/scenes.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(previews, separators=(",", ":")), encoding="utf-8")
    print(f"Exported {len(previews)} deterministic scene layouts")


if __name__ == "__main__":
    main()
