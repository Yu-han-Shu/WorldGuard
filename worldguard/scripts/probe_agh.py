"""Load the product plugins in a production official Host without any inference."""

import argparse
import json
import secrets
from pathlib import Path

from worldguard.api_models import CreateRun
from worldguard.api_service import ApiService
from worldguard.live_runtime import LiveRuntime

parser = argparse.ArgumentParser()
parser.add_argument("--config", default="configs/model_budget.local.json")
args = parser.parse_args()
runtime = LiveRuntime(args.config)
service = ApiService(Path(".local/probe-campaigns"), live=runtime)
try:
    run = service.create(CreateRun(config_id="dual_route_stale", request_id=secrets.token_hex(8), execution_mode="manual"))
    result = runtime.execute(service, run["state"]["run_id"], probe=True)
    assert result["model_requests"] == 0
    print(json.dumps(result))
finally:
    service.close()
