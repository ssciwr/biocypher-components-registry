"""Dependency wiring for the FastAPI application."""

from __future__ import annotations

import secrets as pysecrets
from pathlib import Path
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, Query, Request, status

from src.api.settings import settings
from src.core.auth.models import AuthSession
from src.core.registration.store import RegistrationStore  # Port
from src.core.settings import get_registration_database_path as core_database_path
from src.core.workspace.service import Session, SessionManager
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
    """Create the auth session store used by API routes. Use the same pattern above for test purposes"""
    return build_auth_session_store()


def get_optional_auth_session(
    session_token: str | None = Cookie(
        default=None, alias=settings.auth_session_cookie_name
    ),
) -> AuthSession | None:
    """Return the current session when a browser cookie is present."""
    if session_token is None:
        return None
    return build_auth_session_store().get_session(session_token)


def get_current_auth_session(
    session: AuthSession | None = Depends(get_optional_auth_session),  # noqa: B008
) -> AuthSession:
    """Require a signed-in GitHub session."""
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="GitHub sign-in required.",
        )
    return session


# ===========================================================
# Workspace (Agentic Workspace) Dependencies
# ===========================================================


def get_session_manager(request: Request) -> SessionManager:
    """Return the app-lifetime session manager set up by the API lifespan."""
    return request.app.state.workspace_manager


def get_workspace_session(
    session_id: str,
    manager: Annotated[SessionManager, Depends(get_session_manager)],
    auth_session: Annotated[AuthSession, Depends(get_current_auth_session)],
    authorization: Annotated[str | None, Header()] = None,
    token: Annotated[str | None, Query()] = None,
) -> Session:
    """Resolve a workspace session for the current GitHub user.

    Unknown sessions, owner mismatches, and invalid tokens all return the same
    401 response.
    """
    session = manager.get(session_id)
    supplied = token or ""
    if not supplied and authorization and authorization.startswith("Bearer "):
        supplied = authorization[len("Bearer ") :].strip()
    if session is None or not supplied:
        raise HTTPException(401, "unknown session or invalid session token")
    if session.owner_github_user_id != auth_session.github_user_id:
        raise HTTPException(401, "unknown session or invalid session token")
    if not pysecrets.compare_digest(supplied, session.token):
        raise HTTPException(401, "unknown session or invalid session tokenn")
    return session
