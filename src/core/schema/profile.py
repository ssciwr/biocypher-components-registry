"""Schema profile management.

Defines the active validation profile version and exposes a loader
that reads the corresponding JSON Schema file from the same directory.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

ACTIVE_PROFILE_VERSION: str = "v1"

_SCHEMA_FILE_MAP: Dict[str, str] = {
    "v1": "croissant_v1.json",
}

_SCHEMA_DIR = Path(__file__).parent


def load_active_schema() -> Dict[str, Any]:
    return load_schema(ACTIVE_PROFILE_VERSION)


def load_schema(version: str) -> Dict[str, Any]:
    filename = _SCHEMA_FILE_MAP.get(version)
    if filename is None:
        registered = ", ".join(sorted(_SCHEMA_FILE_MAP))
        raise ValueError(
            f"Unknown schema version {version!r}. "
            f"Registered versions: {registered}"
        )

    schema_path = _SCHEMA_DIR / filename
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    with schema_path.open(encoding="utf-8") as fh:
        return json.load(fh)
