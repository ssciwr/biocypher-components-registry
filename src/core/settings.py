"""Shared runtime settings for backend interfaces."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CoreSettings:
    """Configuration values shared by API, CLI, and registration workflows."""

    database_url_env: str = "DATABASE_URL"
    registry_db_path_env: str = "BIOCYPHER_REGISTRY_DB_PATH"
    default_registry_db_path: Path = Path("registry.sqlite3")


settings = CoreSettings()


def get_database_url() -> str | None:
    """Return the PostgreSQL database URL when configured.

    Returns:
        Database URL if DATABASE_URL environment variable is set, None otherwise.
    """
    return os.getenv(settings.database_url_env)


def get_registration_database_path(
    database_path: str | Path | None = None,
) -> Path:
    """Return the explicit, environment, or default registry database path.

    Used for SQLite database file location. Ignored when DATABASE_URL is set.
    """
    if database_path is not None:
        return Path(database_path)

    return Path(
        os.getenv(
            settings.registry_db_path_env,
            str(settings.default_registry_db_path),
        )
    )
