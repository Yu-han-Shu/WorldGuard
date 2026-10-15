import json
import platform
import shutil
import subprocess

report = {"os": platform.platform(), "shell": "PowerShell", "python": platform.python_version()}
for tool, args in (("git", ["--version"]), ("node", ["--version"]), ("pnpm.cmd", ["--version"])):
    executable = shutil.which(tool)
    report[tool] = (
        None
        if not executable
        else subprocess.run(
            [executable, *args], check=False, capture_output=True, text=True, timeout=15
        ).stdout.strip()
    )
print(json.dumps(report, indent=2))
