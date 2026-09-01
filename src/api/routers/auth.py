"""GitHub OAuth routes."""

from __future__ import annotations

import hmac
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from typing import Annotated, Any
from urllib.parse import urlencode

import requests
from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.responses import RedirectResponse

from src.api.dependencies import get_auth_session_store, get_current_auth_session
from src.api.schemas.auth import AuthMeResponse
from src.api.settings import settings
from src.core.auth.models import AuthSession
from src.persistence.auth_store import AuthSessionStore

router = APIRouter()
AuthSessionCookie = Annotated[
    str | None,
    Cookie(alias=settings.auth_session_cookie_name),
]
AuthSessionStoreDependency = Annotated[
    AuthSessionStore,
    Depends(get_auth_session_store),
]
CurrentAuthSessionDependency = Annotated[
    AuthSession,
    Depends(get_current_auth_session),
]


@router.get("/auth/github/start", include_in_schema=False)
def start_github_oauth(return_to: str | None = None) -> RedirectResponse:
    """Redirect the browser to GitHub's OAuth consent screen."""
    client_id, _, session_secret = _github_oauth_config()
    state = token_urlsafe(24)
    params = {
        "client_id": client_id,
        "redirect_uri": _github_callback_url(),
        "state": state,
    }
    response = RedirectResponse(
        f"https://github.com/login/oauth/authorize?{urlencode(params)}"
    )
    response.set_cookie(
        settings.auth_state_cookie_name,
        _signed_state(state, session_secret),
        httponly=True,
        max_age=600,
        path="/",
        samesite="lax",
        secure=_secure_cookie(),
    )
    response.set_cookie(
        settings.auth_return_to_cookie_name,
        _safe_frontend_path(return_to),
        httponly=True,
        max_age=600,
        path="/",
        samesite="lax",
        secure=_secure_cookie(),
    )
    return response


@router.get("/auth/github/callback", include_in_schema=False)
def finish_github_oauth(
    code: str,
    state: str,
    request: Request,
    store: AuthSessionStoreDependency,
) -> RedirectResponse:
    """Exchange a GitHub OAuth code for a local browser session."""
    client_id, client_secret, session_secret = _github_oauth_config()
    signed_state = request.cookies.get(settings.auth_state_cookie_name)
    if signed_state is None or not hmac.compare_digest(
        signed_state,
        _signed_state(state, session_secret),
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state.",
        )

    token = _github_access_token(client_id, client_secret, code)
    github_user = _github_user(token)
    expires_at = datetime.now(UTC) + timedelta(days=settings.auth_session_days)
    session_token = store.create_session(
        github_user_id=_github_user_id(github_user),
        expires_at=expires_at,
    )
    return_to = _safe_frontend_path(
        request.cookies.get(settings.auth_return_to_cookie_name)
    )
    response = RedirectResponse(f"{settings.frontend_base_url.rstrip('/')}{return_to}")
    response.delete_cookie(settings.auth_state_cookie_name, path="/")
    response.delete_cookie(settings.auth_return_to_cookie_name, path="/")
    response.set_cookie(
        settings.auth_session_cookie_name,
        session_token,
        httponly=True,
        max_age=settings.auth_session_days * 24 * 60 * 60,
        path="/",
        samesite="lax",
        secure=_secure_cookie(),
    )
    return response


@router.get("/auth/me")
def get_me(session: CurrentAuthSessionDependency) -> AuthMeResponse:
    """Return the current signed-in GitHub identity."""
    return AuthMeResponse.from_session(session)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    store: AuthSessionStoreDependency,
    session_token: AuthSessionCookie = None,
) -> None:
    """Delete the local browser session cookie."""
    if session_token is not None:
        store.delete_session(session_token)
    response.delete_cookie(settings.auth_session_cookie_name, path="/")


def _github_oauth_config() -> tuple[str, str, str]:
    """Read required GitHub OAuth settings."""
    if not settings.github_oauth_client_id or not settings.github_oauth_client_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub OAuth is not configured.",
        )
    if not settings.auth_session_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth session secret is not configured.",
        )
    return (
        settings.github_oauth_client_id,
        settings.github_oauth_client_secret,
        settings.auth_session_secret,
    )


def _github_callback_url() -> str:
    """Build the callback URL registered with GitHub."""
    return f"{settings.api_base_url}{settings.api_v1_prefix}/auth/github/callback"


def _github_access_token(client_id: str, client_secret: str, code: str) -> str:
    """Exchange GitHub's temporary code for an access token."""
    response = requests.post(
        "https://github.com/login/oauth/access_token",
        headers={"Accept": "application/json"},
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": _github_callback_url(),
        },
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    token = _optional_text(payload.get("access_token"))
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub login failed.",
        )
    return token


def _github_user(access_token: str) -> dict[str, Any]:
    """Fetch the signed-in GitHub account identity."""
    response = requests.get(
        "https://api.github.com/user",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {access_token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    _github_user_id(payload)
    return payload


def _github_user_id(payload: dict[str, Any]) -> str:
    """Extract GitHub's stable numeric user id as a string."""
    raw_user_id = payload.get("id")
    if type(raw_user_id) is int and raw_user_id > 0:
        return str(raw_user_id)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="GitHub login failed.",
    )


def _signed_state(state: str, secret: str) -> str:
    """Sign OAuth state so it can be validated without storing it."""
    signature = hmac.new(
        secret.encode("utf-8"),
        state.encode("utf-8"),
        sha256,
    ).hexdigest()
    return f"{state}.{signature}"


def _safe_frontend_path(value: str | None) -> str:
    """Return a same-site frontend path for post-login redirects."""
    if value is None:
        return "/"
    normalized = value.strip()
    if not normalized.startswith("/") or normalized.startswith("//"):
        return "/"
    return normalized


def _secure_cookie() -> bool:
    """Use secure cookies when the backend runs over HTTPS."""
    return settings.api_base_url.startswith("https://")


def _optional_text(value: object) -> str | None:
    """Normalize optional GitHub JSON string fields."""
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None
