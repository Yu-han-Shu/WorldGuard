"""Run a finite acceptance command and preserve exact invocation, output and exit code."""

import argparse
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("batch")
    parser.add_argument("label")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    destination = root / "artifacts" / "batches" / args.batch
    destination.mkdir(parents=True, exist_ok=True)
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    command = [sys.executable if item == "PYTHON" else item for item in command]
    start = time.monotonic()
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    result = subprocess.run(
        command,
        check=False,
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
        env=env,
    )
    output = result.stdout + result.stderr
    # No credential-reading commands may be passed. Redact known private directory prefixes.
    for private, label in ((str(root.parent), "WORKSPACE"), (str(Path.home()), "USER_HOME")):
        output = output.replace(private, label).replace(private.replace("\\", "/"), label)
    (destination / f"{args.label}.txt").write_text(output, encoding="utf-8")
    record = {
        "command": ["PYTHON" if x == sys.executable else x for x in command],
        "cwd": "PROJECT_ROOT",
        "exit_code": result.returncode,
        "timestamp": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        "elapsed_seconds": time.monotonic() - start,
        "output": f"artifacts/batches/{args.batch}/{args.label}.txt",
    }
    with (destination / "commands.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(json.dumps(record, ensure_ascii=False))
    print(output[-6000:])
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
