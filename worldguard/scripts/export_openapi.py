"""Export the exact runtime schema used to generate frontend TypeScript types."""

import json
from pathlib import Path

from worldguard.api import create_app

root = Path(__file__).resolve().parents[1]
app = create_app(root / ".local/openapi-unused")
try:
    (root / "frontend/openapi.json").write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
finally:
    app.state.service.close()
