"""Capability inspection. Never reads credential contents or prints private paths."""

import importlib.metadata
import importlib.util
import json
import platform
import shutil
import sys
from pathlib import Path


def inspect():
    root = Path(__file__).resolve().parents[1]
    dependencies = {}
    for name in ("worldguard", "pytest", "mcp", "streamlit", "numpy", "scipy", "open3d"):
        available = importlib.util.find_spec(name) is not None
        try:
            version = importlib.metadata.version(name) if available else None
        except importlib.metadata.PackageNotFoundError:
            version = None
        dependencies[name] = {"available": available, "version": version}
    return {
        "os": platform.system(),
        "python": platform.python_version(),
        "isolated": sys.prefix != sys.base_prefix,
        "tools": {name: shutil.which(name) is not None for name in ("git", "node", "pnpm")},
        "dependencies": dependencies,
        "local_config_present": (root / "configs/local.json").is_file(),
        "credential_values_inspected": False,
        "external_model_calls_allowed": False,
        "path_labels": {"project": "PROJECT_ROOT", "pack": "PACK_ROOT"},
    }


if __name__ == "__main__":
    print(json.dumps(inspect(), indent=2))
