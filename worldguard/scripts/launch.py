"""Launch the workbench and, if needed, its local API."""

import argparse
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from worldguard.workbench_client import WorkbenchClient, WorkbenchError


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8510)
    parser.add_argument("--api-port", type=int, default=8520)
    parser.add_argument("--live-config", help="Explicit, locally authorized model budget file")
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args()
    if any(not 1024 <= port <= 65535 for port in (args.port, args.api_port)):
        parser.error("ports must be in 1024..65535")
    if args.port == args.api_port:
        parser.error("UI and API ports must differ")
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    api_url = f"http://127.0.0.1:{args.api_port}"
    env["WORLDGUARD_API_URL"] = api_url
    if args.live_config:
        config = Path(args.live_config)
        config = (root / config).resolve()
        if not config.is_file():
            parser.error("LIVE config missing; follow docs/AGH_LIVE.md")
        env["WORLDGUARD_LIVE_CONFIG"] = str(config)
    client = WorkbenchClient(api_url)
    backend = None
    keep_backend = False
    try:
        try:
            health = client.request("/health")
            if health.get("api_version") != "1.0.0" or health.get("status") != "ok":
                raise RuntimeError("Unexpected API service on the requested port")
            if args.live_config and not health.get("external_model_calls_allowed"):
                raise RuntimeError("Existing API has LIVE disabled; restart that API with your live config")
        except WorkbenchError:
            backend = subprocess.Popen(
                [sys.executable, "-m", "worldguard.api", "--port", str(args.api_port)],
                cwd=root, env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            for _ in range(40):
                if backend.poll() is not None:
                    raise RuntimeError("API startup failed; see its diagnostic output")
                try:
                    client.request("/health")
                    break
                except WorkbenchError:
                    time.sleep(0.25)
            else:
                raise RuntimeError("API did not become ready")
        ui_url = f"http://127.0.0.1:{args.port}"
        try:
            with urlopen(ui_url + "/_stcore/health", timeout=2) as response:
                ui_running = response.read().strip() == b"ok"
        except (URLError, OSError):
            ui_running = False
        if args.open_browser:
            # Streamlit starts immediately below; the browser may briefly show its loading screen.
            webbrowser.open(ui_url)
        if ui_running:
            keep_backend = True
            print("Workbench already running: " + ui_url)
            return 0
        return subprocess.call(
            [sys.executable, "-m", "streamlit", "run", str(root / "app.py"),
             "--server.address", "127.0.0.1", "--server.port", str(args.port),
             "--server.headless", "true", "--browser.gatherUsageStats", "false"],
            cwd=root, env=env,
        )
    finally:
        if backend is not None and not keep_backend:
            # Leave active work alive; never interrupt a model call just because UI closed.
            try:
                busy = any(r["job_active"] for r in client.request("/runs?limit=100")["items"])
            except WorkbenchError:
                busy = True
            if not busy:
                backend.terminate()
                backend.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
