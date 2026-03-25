"""Factory helpers for persistence adapters."""

from __future__ import annotations

from pathlib import Path

from src.core.registration.store import RegistrationStore
from src.core.settings import get_registration_database_path
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore


def build_registration_store(
    database_path: str | Path | None = None,
) -> RegistrationStore:
    """Create the configured registration store adapter."""
    return SQLiteRegistrationStore(get_registration_database_path(database_path))
