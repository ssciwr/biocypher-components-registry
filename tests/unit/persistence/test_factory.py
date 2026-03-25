from __future__ import annotations

from pathlib import Path

from src.core.settings import get_registration_database_path, settings
from src.persistence.factory import build_registration_store
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore


def test_registration_database_path_uses_explicit_path(tmp_path: Path) -> None:
    """An explicit database path wins over environment and default settings."""
    database_path = tmp_path / "registry.sqlite3"

    assert get_registration_database_path(database_path) == database_path


def test_registration_database_path_uses_environment_override(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Shared settings expose the deployment database path override."""
    database_path = tmp_path / "registry.sqlite3"
    monkeypatch.setenv(settings.registry_db_path_env, str(database_path))

    assert get_registration_database_path() == database_path


def test_registration_store_factory_builds_sqlite_store(tmp_path: Path) -> None:
    """The current persistence factory creates the SQLite registration adapter."""
    database_path = tmp_path / "registry.sqlite3"

    store = build_registration_store(database_path)

    assert isinstance(store, SQLiteRegistrationStore)
