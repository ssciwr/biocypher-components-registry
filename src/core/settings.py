"""Shared runtime settings for backend interfaces."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.engine import URL


@dataclass(frozen=True, slots=True)
class CoreSettings:
    """Configuration values shared by API, CLI, and registration workflows."""

    github_oauth_client_id_env: str = "GITHUB_OAUTH_CLIENT_ID"
    github_oauth_client_secret_env: str = "GITHUB_OAUTH_CLIENT_SECRET"
    database_url_env: str = "DATABASE_URL"
    registry_db_path_env: str = "BIOCYPHER_REGISTRY_DB_PATH"
    default_registry_db_path: Path = Path("registry.sqlite3")


settings = CoreSettings()


def get_database_url() -> str | URL | None:
    """Return the PostgreSQL database URL when configured.

    Returns:
        Database URL if DATABASE_URL environment variable is set, None otherwise.
    """
    configured = os.getenv(settings.database_url_env, "").strip()
    if configured:
        return configured
    host = os.getenv("POSTGRES_HOST", "").strip()
    if not host:
        return None
    password = os.getenv("POSTGRES_PASSWORD", "")
    if not password:
        raise ValueError("POSTGRES_PASSWORD is required when POSTGRES_HOST is set.")
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    if not 1 <= port <= 65535:
        raise ValueError("POSTGRES_PORT must be between 1 and 65535.")
    return URL.create(
        "postgresql",
        username=os.getenv("POSTGRES_USER", "biocypher"),
        password=password,
        host=host,
        port=port,
        database=os.getenv("POSTGRES_DB", "biocypher_registry"),
    )


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
