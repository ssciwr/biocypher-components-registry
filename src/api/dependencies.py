"""Dependency wiring for the FastAPI application."""

from __future__ import annotations

from pathlib import Path

from src.core.settings import get_registration_database_path as core_database_path
from src.core.registration.store import RegistrationStore  # Port
from src.persistence.factory import build_registration_store  # Adapter factory


# ===========================================================
# Persistence Dependencies
# ===========================================================


def get_registration_database_path() -> Path:
    """Return the configured registration database path."""
    return core_database_path()


def get_registration_store() -> RegistrationStore:
    """Create the registration store used by API routes."""
    return build_registration_store()
