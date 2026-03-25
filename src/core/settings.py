"""Shared runtime settings for backend interfaces."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CoreSettings:
    """Configuration values shared by API, CLI, and legacy web delivery layers."""

    registry_db_path_env: str = "BIOCYPHER_REGISTRY_DB_PATH"
    default_registry_db_path: Path = Path("registry.sqlite3")


settings = CoreSettings()


def get_registration_database_path(
    database_path: str | Path | None = None,
) -> Path:
    """Return the explicit, environment, or default registry database path."""
    if database_path is not None:
        return Path(database_path)

    return Path(
        os.getenv(
            settings.registry_db_path_env,
            str(settings.default_registry_db_path),
        )
    )
