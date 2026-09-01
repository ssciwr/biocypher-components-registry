"""Pydantic schemas for auth API responses."""

from __future__ import annotations

from pydantic import BaseModel

from src.core.auth.models import AuthSession


class AuthMeResponse(BaseModel):
    """Browser-safe signed-in state."""

    authenticated: bool

    @classmethod
    def from_session(cls, session: AuthSession) -> AuthMeResponse:
        """Build the browser-safe auth response."""
        _ = session
        return cls(authenticated=True)
