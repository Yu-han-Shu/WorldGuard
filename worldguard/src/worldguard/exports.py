import io
import zipfile

from worldguard.contracts import identifier


def export_run(root, run_id):
    identifier(run_id)
    folder = (root / run_id).resolve()
    if folder.parent != root.resolve() or not folder.is_dir():
        raise ValueError("UNKNOWN_RUN")
    buffer = io.BytesIO()
    allowed_names = {"report.json", "report.md", "events.jsonl", "state.json", "agh_summary.json", "agh_session.jsonl"}
    allowed_names.add("execution_error.json")
    allowed_names.update({"mission.json", "agent_decisions.json", "submission.json", "evidence_chat.json"})
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        total = 0
        for path in sorted(folder.rglob("*")):
            relative = path.relative_to(folder)
            if path.is_symlink() or (path.is_file() and folder not in path.resolve().parents):
                raise ValueError("EXPORT_ESCAPE")
            if not path.is_file() or path.suffix not in (".json", ".jsonl", ".md"):
                continue
            if relative.parts[0] not in ("cases", "evidence", "optimization", "experiments") and path.name not in allowed_names:
                continue
            total += path.stat().st_size
            if total > 20_000_000:
                raise ValueError("EXPORT_TOO_LARGE")
            archive.write(path, relative.as_posix())
    return buffer.getvalue()
