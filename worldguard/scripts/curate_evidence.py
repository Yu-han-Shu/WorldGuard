"""Copy only known local batch records into a sanitized release evidence directory."""

import json
import sys
from pathlib import Path

from package_release import SECRET_PATTERN

root = Path(__file__).resolve().parents[1]
count = 0
for source in (root / "artifacts/batches").glob("R*/*"):
    if not source.is_file() or source.suffix not in (".txt", ".json", ".jsonl", ".md", ".png"):
        continue
    destination = root / "evidence/batches" / source.parent.name / source.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = source.read_bytes()
    if source.suffix != ".png":
        content = data.decode("utf-8-sig", errors="replace")
        for private, label in (
            (str(root.parent), "WORKSPACE"),
            (str(Path.home()), "USER_HOME"),
            (sys.base_prefix, "PYTHON_BASE"),
        ):
            for form in (private.replace("\\", "\\\\"), private, private.replace("\\", "/")):
                content = content.replace(form, label)
        data = content.encode("utf-8")
        if SECRET_PATTERN.search(data):
            raise ValueError("SUSPECT_SECRET_IN_CURATED_EVIDENCE")
    destination.write_bytes(data)
    count += 1
print(json.dumps({"curated_files": count, "destination": "evidence/batches"}))
