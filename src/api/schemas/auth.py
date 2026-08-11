"""Pydantic schemas for auth API responses."""

from __future__ import annotations

from pydantic import BaseModel

from src.core.auth.models import AuthSession


class AuthMeResponse(BaseModel):
    """Signed-in GitHub identity shown in the frontend header."""

    github_login: str

    @classmethod
    def from_session(cls, session: AuthSession) -> AuthMeResponse:
        """Build the browser-safe auth response."""
        return cls(
            github_login=session.github_login,
        )
