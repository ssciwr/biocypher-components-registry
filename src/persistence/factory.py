"""Configured, process-local persistence adapters shared by API and CLI."""

from pathlib import Path
from threading import RLock

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from src.core.registration.store import RegistrationStore
from src.core.settings import (
    DatabaseBackend,
    DatabaseSettings,
    load_database_settings,
)
from src.persistence.auth_store import AuthSessionStore
from src.persistence.errors import DatabaseSetupError
from src.persistence.registration_postgres_store import PostgreSQLRegistrationStore
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore

_stores: dict[tuple[str, str], RegistrationStore] = {}
_auth_stores: dict[tuple[str, str], AuthSessionStore] = {}
_store_lock = RLock()


def _resolved_settings(database_path, database_settings=None):
    return database_settings or load_database_settings(database_path)


def _store_key(database_settings: DatabaseSettings) -> tuple[str, str]:
    if database_settings.backend is DatabaseBackend.SQLITE:
        assert database_settings.sqlite_database_path is not None
        return (
            database_settings.backend.value,
            str(database_settings.sqlite_database_path.resolve()),
        )
    assert database_settings.postgres_url is not None
    return (
        database_settings.backend.value,
        database_settings.postgres_url.render_as_string(hide_password=False),
    )


def build_registration_store(
    database_path: str | Path | None = None,
    *,
    database_settings: DatabaseSettings | None = None,
) -> RegistrationStore:
    """Initialize once per process/configuration, then reuse the store and engine.

    The explicit backend selects PostgreSQL or SQLite. ``database_path`` is a
    SQLite-only override used by CLI commands and tests.
    """
    configured = _resolved_settings(database_path, database_settings)
    key = _store_key(configured)
    with _store_lock:
        if key not in _stores:
            try:
                if configured.backend is DatabaseBackend.POSTGRESQL:
                    assert configured.postgres_url is not None
                    _stores[key] = PostgreSQLRegistrationStore(
                        configured.postgres_url
                    )
                else:
                    assert configured.sqlite_database_path is not None
                    _stores[key] = SQLiteRegistrationStore(
                        configured.sqlite_database_path
                    )
            except (SQLAlchemyError, OSError, ValueError):
                raise DatabaseSetupError(
                    "Database setup failed. Check the selected database and credentials; "
                    "adapter processing did not start."
                ) from None
        return _stores[key]


def build_auth_session_store(
    database_path: str | Path | None = None,
    *,
    database_settings: DatabaseSettings | None = None,
) -> AuthSessionStore:
    """Reuse the configured registry engine for browser authentication."""
    configured = _resolved_settings(database_path, database_settings)
    key = _store_key(configured)
    with _store_lock:
        if key not in _auth_stores:
            _auth_stores[key] = AuthSessionStore(
                build_registration_store(
                    database_path,
                    database_settings=configured,
                ).engine
            )
        return _auth_stores[key]


def close_stores() -> None:
    """Dispose owned engines at application shutdown or test teardown."""
    with _store_lock:
        for store in _stores.values():
            store.engine.dispose()
        _auth_stores.clear()
        _stores.clear()


def check_database_connection(
    database_path: str | Path | None = None,
    *,
    database_settings: DatabaseSettings | None = None,
) -> str:
    """Check PostgreSQL read-only before OAuth; do not create a SQLite file."""
    engine = None
    try:
        configured = _resolved_settings(database_path, database_settings)
        if configured.backend is DatabaseBackend.SQLITE:
            assert configured.sqlite_database_path is not None
            return f"SQLite ({configured.sqlite_database_path.resolve()})"
        assert configured.postgres_url is not None
        parsed = make_url(configured.postgres_url)
        if parsed.get_backend_name() != "postgresql":
            raise ValueError("The configured database must be PostgreSQL.")
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
