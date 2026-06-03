"""Dependency wiring for the FastAPI application."""

from __future__ import annotations

from pathlib import Path

from fastapi import Cookie, Depends, HTTPException, status

from src.api.settings import settings
from src.core.auth.models import AuthSession
from src.core.settings import get_registration_database_path as core_database_path
from src.core.registration.store import RegistrationStore  # Port
from src.persistence.auth_store import AuthSessionStore
from src.persistence.factory import build_auth_session_store, build_registration_store


# ===========================================================
# Persistence Dependencies
# ===========================================================


def get_registration_database_path() -> Path:
    """Return the configured registration database path."""
    return core_database_path()


def get_registration_store() -> RegistrationStore:
    """Create the registration store used by API routes."""
    return build_registration_store()


def get_auth_session_store() -> AuthSessionStore:
    """ Create the auth session store used by API routes. Use the same pattern above for test purposes"""
    return build_auth_session_store()


def get_optional_auth_session(
    session_token: str | None = Cookie(default=None, alias=settings.auth_session_cookie_name),
) -> AuthSession | None:
    """Return the current session when a browser cookie is present."""
    if session_token is None:
        return None
    return build_auth_session_store().get_session(session_token)


def get_current_auth_session(
    session: AuthSession | None = Depends(get_optional_auth_session),
) -> AuthSession:
    """ Require a signed-in GitHub session."""
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="GitHub sign-in required.",
        )
    return session
