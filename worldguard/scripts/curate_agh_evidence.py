"""Publish only reviewed evidence, never launch recipes, AGH homes, keys or raw reasoning."""

import hashlib
import json
import sys
from pathlib import Path

from package_release import SECRET_PATTERN

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / "artifacts/batches/AGH_LIVE"
TARGET = ROOT / "evidence/batches/AGH_LIVE"


def checked_copy(source, destination, *, log=False):
    data = source.read_bytes()
    if log:
        content = data.decode("utf-8-sig", errors="replace")
        for private, label in ((str(ROOT.parent), "WORKSPACE"), (str(Path.home()), "USER_HOME"),
                               (sys.base_prefix, "PYTHON_BASE")):
            for form in (private.replace("\\", "\\\\"), private, private.replace("\\", "/")):
                content = content.replace(form, label)
        data = content.encode("utf-8")
    if SECRET_PATTERN.search(data) or b"E:\\agnes-hackathon" in data or b"C:\\Users\\" in data:
        raise ValueError("PRIVATE_DATA_IN_EVIDENCE")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)


def main():
    for source in BATCH.iterdir():
        if source.is_file() and source.suffix in (".txt", ".json", ".jsonl", ".md") and ".local." not in source.name:
            checked_copy(source, TARGET / source.name, log=True)
    run_status = []
    for folder in sorted((ROOT / "artifacts/live-campaigns").glob("run_*")):
        if not (folder / "report.json").is_file():
            continue
        for source in folder.rglob("*"):
            if source.is_symlink():
                raise ValueError("EVIDENCE_ESCAPE")
            if not source.is_file() or source.suffix not in (".json", ".jsonl", ".md"):
                continue
            checked_copy(source, TARGET / "runs" / folder.name / source.relative_to(folder))
        report = json.loads((folder / "report.json").read_text(encoding="utf-8"))
        run_status.append({"run_id": folder.name, "status": report["status"],
                           "executed_cases": report["executed_cases"], "planned_cases": report["planned_cases"],
                           "model_requests": report["model_requests"]})
    authorization = {"approval_reference": "2026-10-13 user: 请求也无所谓；反正是免费模型；全部走一遍",
                     "provider": "Agnes", "max_total_requests": 120, "max_requests_per_run": 30,
                     "max_output_tokens_per_request": 2000, "max_wall_seconds_per_run": 180,
                     "cost": None, "scope": "minimum execution chain; no submission or public release"}
    (TARGET / "authorization.json").write_text(json.dumps(authorization, ensure_ascii=False, indent=2), encoding="utf-8")
    (TARGET / "run_index.json").write_text(json.dumps(run_status, indent=2), encoding="utf-8")
    files = {p.relative_to(TARGET).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in TARGET.rglob("*") if p.is_file() and p.name != "MANIFEST.json"}
    (TARGET / "MANIFEST.json").write_text(json.dumps(files, indent=2), encoding="utf-8")
    print(json.dumps({"curated_files": len(files), "runs": len(run_status),
                      "model_requests": sum(r["model_requests"] or 0 for r in run_status)}))


if __name__ == "__main__":
    main()
