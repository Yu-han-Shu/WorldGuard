import subprocess
import sys

import worldguard


def test_import_and_cli():
    assert worldguard.__version__ == "0.1.0"
    result = subprocess.run(
        [sys.executable, "-m", "worldguard.cli", "--help"], check=False, capture_output=True
    )
    assert result.returncode == 0
    assert b"WorldGuard" in result.stdout
