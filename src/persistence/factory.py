"""Factory helpers for persistence adapters."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine

from src.core.registration.store import RegistrationStore
from src.core.settings import get_database_url, get_registration_database_path
from src.persistence.auth_store import AuthSessionStore
from src.persistence.registration_postgres_store import PostgreSQLRegistrationStore
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore


def build_registration_store(
    database_path: str | Path | None = None,
) -> RegistrationStore:
    """Create the configured registration store adapter.

    Selects between PostgreSQL and SQLite based on DATABASE_URL environment variable:
    - If DATABASE_URL is set: Use PostgreSQL
    - Otherwise: Use SQLite (development default)

    Args:
        database_path: Optional SQLite database path (ignored if DATABASE_URL is set)

    Returns:
        RegistrationStore implementation (PostgreSQL or SQLite)
    """
    database_url = get_database_url()

    if database_url is not None:
        return PostgreSQLRegistrationStore(database_url)

    return SQLiteRegistrationStore(get_registration_database_path(database_path))


def build_auth_session_store(
    database_path: str | Path | None = None,
) -> AuthSessionStore:
    """Create the local GitHub auth session store (SQL lite database)."""
    database_url = get_database_url()
    if database_url is not None:
        return AuthSessionStore(create_engine(database_url, pool_pre_ping=True))

    resolved_path = get_registration_database_path(database_path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    return AuthSessionStore(create_engine(f"sqlite+pysqlite:///{resolved_path}"))
