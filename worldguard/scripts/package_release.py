"""Build a local candidate from explicit roots; validate member paths and content hashes."""

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "README.md",
    "RUN.md",
    "AGENTS.md",
    "pyproject.toml",
    "requirements.lock",
    "app.py",
    "start-worldguard.ps1",
    "start-worldguard.cmd",
    "start-worldguard-live.cmd",
    "start-worldguard.sh",
    "start-api.cmd",
    ".gitignore",
]
DIRECTORIES = [
    "src", "tests", "scripts", "docs", "prompts", "scenarios", "experiments", "evidence",
    "frontend", "agh_plugin",
]
SECRET_PATTERN = re.compile(rb"(?:sk-[A-Za-z0-9]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)")


def package(*, runnable=False):
    sources = [ROOT / name for name in FILES]
    sources.append(ROOT / "configs/model_budget.example.json")
    for directory in DIRECTORIES:
        sources.extend(
            path
            for path in (ROOT / directory).rglob("*")
            if path.is_file() and not {"__pycache__", "node_modules"}.intersection(path.parts)
            and path.suffix != ".pyc"
            and (not path.name.startswith(".env") or path.name == ".env.example")
        )
    members = {}
    for source in sorted(sources):
        if source.is_symlink() or ROOT not in source.resolve().parents:
            raise ValueError("SOURCE_ESCAPE")
        relative = source.relative_to(ROOT).as_posix()
        if source.stat().st_size > 5_000_000:
            raise ValueError("UNEXPECTED_LARGE_FILE")
        data = source.read_bytes()
        if SECRET_PATTERN.search(data):
            raise ValueError("SUSPECT_SECRET: " + relative)
        if b"E:\\agnes-hackathon" in data or b"C:\\Users\\" in data:
            raise ValueError("PRIVATE_ABSOLUTE_PATH: " + relative)
        members[relative] = data
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in members.items()}
    members["RELEASE_MANIFEST.json"] = json.dumps(manifest, indent=2).encode()
    members["BUILD_INFO.json"] = json.dumps(
        {
            "type": "LOCAL_RUNNABLE_MVP" if runnable else "LOCAL_RELEASE_CANDIDATE",
            "LIVE": "SEE_AGH_LIVE_EVIDENCE",
            "default_runtime": "DETERMINISTIC",
            "competition_ready": False,
            "manifest_sha256": hashlib.sha256(members["RELEASE_MANIFEST.json"]).hexdigest(),
        }
    ).encode()
    output = ROOT / "dist" / ("worldguard_desktop_mvp.zip" if runnable else "worldguard_release_candidate.zip")
    output.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(members.items()):
            archive.writestr(name, data)
    validate(output)
    (output.parent / "SHA256SUMS.txt").write_text(
        hashlib.sha256(output.read_bytes()).hexdigest() + "  " + output.name + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "archive": "dist/" + output.name,
                "files": len(members),
                "bytes": output.stat().st_size,
                "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "integrity": "PASS",
            }
        )
    )
    return output


def validate(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("DUPLICATE_MEMBERS")
        for name in names:
            member = PurePosixPath(name)
            if member.is_absolute() or ".." in member.parts or "\\" in name or ":" in name:
                raise ValueError("ARCHIVE_ESCAPE")
        manifest = json.loads(archive.read("RELEASE_MANIFEST.json"))
        if set(names) != set(manifest) | {"RELEASE_MANIFEST.json", "BUILD_INFO.json"}:
            raise ValueError("MANIFEST_MEMBERS_MISMATCH")
        for name, expected in manifest.items():
            if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                raise ValueError("HASH_MISMATCH")
        if archive.testzip() is not None:
            raise ValueError("ZIP_CORRUPT")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--runnable", action="store_true", help="Package the runnable workbench MVP")
    package(runnable=parser.parse_args().runnable)
