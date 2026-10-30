"""Configured, process-local persistence adapters shared by API and CLI."""

from pathlib import Path
from threading import RLock

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError

from src.core.registration.store import RegistrationStore
from src.core.settings import get_database_url, get_registration_database_path
from src.persistence.auth_store import AuthSessionStore
from src.persistence.errors import DatabaseSetupError
from src.persistence.registration_postgres_store import PostgreSQLRegistrationStore
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore

_stores: dict[tuple[str | URL | None, str], RegistrationStore] = {}
_auth_stores: dict[tuple[str | URL | None, str], AuthSessionStore] = {}
_store_lock = RLock()


def _store_key(database_path):
    url = get_database_url()
    return (
        url,
        "" if url else str(get_registration_database_path(database_path).resolve()),
    )


def build_registration_store(
    database_path: str | Path | None = None,
) -> RegistrationStore:
    """Initialize once per process/configuration, then reuse the store and engine.

    DATABASE_URL selects PostgreSQL; otherwise database_path or the configured
    SQLite path is used. Schema creation supports only the current schema.
    """
    key = _store_key(database_path)
    with _store_lock:
        if key not in _stores:
            url, path = key
            try:
                _stores[key] = (
                    PostgreSQLRegistrationStore(url)
                    if url
                    else SQLiteRegistrationStore(path)
                )
            except (SQLAlchemyError, OSError, ValueError):
                raise DatabaseSetupError(
                    "Database setup failed. Check the selected database and credentials; "
                    "adapter processing did not start."
                ) from None
        return _stores[key]


def build_auth_session_store(
    database_path: str | Path | None = None,
) -> AuthSessionStore:
    """Reuse the configured registry engine for browser authentication."""
    key = _store_key(database_path)
    with _store_lock:
        if key not in _auth_stores:
            _auth_stores[key] = AuthSessionStore(
                build_registration_store(database_path).engine
            )
        return _auth_stores[key]


def close_stores() -> None:
    """Dispose owned engines at application shutdown or test teardown."""
    with _store_lock:
        for store in _stores.values():
            store.engine.dispose()
        _auth_stores.clear()
        _stores.clear()


def check_database_connection(database_path: str | Path | None = None) -> str:
    """Check PostgreSQL read-only before OAuth; do not create a SQLite file."""
    engine = None
    try:
        url = get_database_url()
        if url is None:
            return f"SQLite ({get_registration_database_path(database_path).resolve()})"
        parsed = make_url(url)
        if parsed.get_backend_name() != "postgresql":
            raise ValueError("DATABASE_URL must select PostgreSQL.")
        engine = create_engine(parsed, connect_args={"connect_timeout": 5})
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return f"PostgreSQL ({parsed.host}:{parsed.port or 5432}/{parsed.database})"
    except (SQLAlchemyError, OSError, ValueError):
        raise DatabaseSetupError(
            "Cannot connect to the configured PostgreSQL database. "
            "Check its Docker service and credentials; adapter processing did not start."
        ) from None
    finally:
        if engine is not None:
            engine.dispose()
