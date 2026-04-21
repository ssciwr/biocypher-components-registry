"""Versioned schema profile loading for adapter validation."""

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
    """Load the schema for the currently active profile version."""
    return load_schema(ACTIVE_PROFILE_VERSION)


def load_schema(version: str) -> Dict[str, Any]:
    """Load a schema by registered profile version.

    Args:
        version: Version key declared in ``_SCHEMA_FILE_MAP``.

    Returns:
        The parsed JSON schema document.
    """
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
