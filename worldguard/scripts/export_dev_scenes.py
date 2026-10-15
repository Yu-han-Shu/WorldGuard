from dataclasses import asdict
from pathlib import Path

from worldguard.evidence import write_json
from worldguard.scene import DEV_SEEDS, FAMILIES, make_scene

for family, seed in zip(FAMILIES, DEV_SEEDS):
    scene, task = make_scene(family, seed)
    out = Path("scenarios/dev") / (family + ".json")
    write_json(out, {"scene": asdict(scene), "task": asdict(task), "seed": seed})
    print(f"{out}: {scene.content_hash}")
