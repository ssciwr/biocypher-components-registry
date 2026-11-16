"""Shared runtime settings for backend interfaces."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from sqlalchemy.engine import URL


class DatabaseBackend(StrEnum):
    """Supported persistence backends."""

    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    """Validated database configuration for one application process."""

    backend: DatabaseBackend
    sqlite_database_path: Path | None = None
    postgres_url: URL | None = None


@dataclass(frozen=True, slots=True)
class CoreSettings:
    """Configuration names shared by API, CLI, and registration workflows."""

    github_oauth_client_id_env: str = "GITHUB_OAUTH_CLIENT_ID"
    github_oauth_client_secret_env: str = "GITHUB_OAUTH_CLIENT_SECRET"
    database_backend_env: str = "DATABASE_BACKEND"
    sqlite_database_path_env: str = "SQLITE_DATABASE_PATH"
    default_sqlite_database_path: Path = Path("registry.sqlite3")


settings = CoreSettings()


def _required_environment(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required.")
    return value


def load_database_settings(
    database_path: str | Path | None = None,
) -> DatabaseSettings:
    """Read and validate the explicitly selected database backend."""
    raw_backend = _required_environment(settings.database_backend_env).lower()
    try:
        backend = DatabaseBackend(raw_backend)
    except ValueError:
        raise ValueError(
            'DATABASE_BACKEND must be either "sqlite" or "postgresql".'
        ) from None

    if backend is DatabaseBackend.SQLITE:
        configured_path = database_path
        if configured_path is None:
            configured_path = _required_environment(settings.sqlite_database_path_env)
        return DatabaseSettings(
            backend=backend,
            sqlite_database_path=Path(configured_path),
        )

    raw_port = _required_environment("POSTGRES_PORT")
    try:
        port = int(raw_port)
    except ValueError:
        raise ValueError("POSTGRES_PORT must be an integer.") from None
    if not 1 <= port <= 65535:
        raise ValueError("POSTGRES_PORT must be between 1 and 65535.")

    return DatabaseSettings(
        backend=backend,
        postgres_url=URL.create(
            "postgresql+psycopg2",
            username=_required_environment("POSTGRES_USER"),
            password=_required_environment("POSTGRES_PASSWORD"),
            host=_required_environment("POSTGRES_HOST"),
            port=port,
            database=_required_environment("POSTGRES_DB"),
        ),
    )


def get_registration_database_path(
    database_path: str | Path | None = None,
) -> Path:
    """Return the configured SQLite path, including an explicit CLI override."""
    if database_path is not None:
        return Path(database_path)

    return Path(_required_environment(settings.sqlite_database_path_env))
