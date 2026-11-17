from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.api.app import create_app
from src.api.routers import workspace
from src.api.settings import settings


# AI-Generated.
def main() -> None:
    # Export the complete frontend contract even when workspace routing is disabled
    # in the running server. Otherwise client regeneration deletes its types.
    app = create_app()
    if not any(
        getattr(route, "path", "").startswith(settings.agent_api_prefix)
        for route in app.routes
    ):
        app.include_router(
            workspace.router, prefix=settings.agent_api_prefix, tags=["workspace"]
        )
    output_path = Path("frontend/src/api/openapi.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(app.openapi(), indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
