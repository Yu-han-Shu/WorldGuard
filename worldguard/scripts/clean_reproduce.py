"""Validate/extract candidate into a NEW local sandbox and install a fresh isolated environment."""

import argparse
import json
import os
import subprocess
import sys
import uuid
import zipfile
from pathlib import Path

from package_release import validate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-only", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    archive = root / "dist/worldguard_release_candidate.zip"
    validate(archive)
    target = root / ".local" / ("clean_" + uuid.uuid4().hex[:10])
    target.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(archive) as zipped:
        zipped.extractall(target)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    env.pop("PYTHONPATH", None)
    commands = []

    def run(command):
        result = subprocess.run(
            command,
            check=False,
            cwd=target,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )
        label = [str(part).replace(str(root), "PROJECT_ROOT") for part in command]
        commands.append(
            {
                "command": label,
                "exit_code": result.returncode,
                "output": (result.stdout + result.stderr).replace(str(root), "PROJECT_ROOT"),
            }
        )
        print(json.dumps({"command": label, "exit_code": result.returncode}), flush=True)
        (target / "clean_commands.json").write_text(json.dumps(commands, indent=2), encoding="utf-8")
        if result.returncode != 0:
            print((result.stdout + result.stderr)[-4000:])
            raise RuntimeError("CLEAN_COMMAND_FAILED")

    if args.smoke_only:
        # Source-only smoke in a second fresh extracted directory, no original editable import.
        env["PYTHONPATH"] = str(target / "src")
        python = sys.executable
        run([python, "-m", "pytest", "-q"])
    else:
        run([sys.executable, "-m", "venv", str(target / ".venv")])
        python = str(target / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
        run([python, "-m", "pip", "install", "-r", "requirements.lock"])
        run([python, "-m", "pip", "install", "--no-build-isolation", "--no-deps", "-e", "."])
        run([python, "-m", "pytest", "-q"])
        run([python, "scripts/mcp_smoke.py"])
    run([python, "-m", "worldguard.cli", "demo", "--out", "artifacts/clean_demo"])
    cases = sorted((target / "artifacts/clean_demo").glob("*/cases/block_route"))
    run([python, "-m", "worldguard.cli", "replay", "--case-dir", str(cases[0]), "--out", "artifacts/replay"])
    run([python, "scripts/summarize_evaluation.py", "--verify"])
    output = root / "artifacts/batches" / ("R08" if args.smoke_only else "R07")
    output.mkdir(parents=True, exist_ok=True)
    (output / "clean_commands.json").write_text(json.dumps(commands, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "REPRODUCED",
                "fresh_environment": not args.smoke_only,
                "target": target.relative_to(root).as_posix(),
                "commands": len(commands),
            }
        )
    )


if __name__ == "__main__":
    main()
