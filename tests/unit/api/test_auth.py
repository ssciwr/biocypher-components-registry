from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from src.api.app import create_app
from src.api.dependencies import get_auth_session_store, get_current_auth_session
from src.api.routers import auth
from src.api.settings import settings
from src.core.auth.models import AuthSession
from src.persistence.auth_store import AuthSessionStore


@pytest.fixture
def auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """AI-Generated.

    Configure deterministic GitHub OAuth settings for route tests.
    """
    monkeypatch.setenv(settings.github_oauth_client_id_env, "client-id")
    monkeypatch.setenv(settings.github_oauth_client_secret_env, "client-secret")
    monkeypatch.setenv(settings.auth_session_secret_env, "session-secret")
    monkeypatch.setenv(settings.frontend_base_url_env, "http://localhost:5173")
    monkeypatch.setenv(settings.api_base_url_env, "http://localhost:8000")


def _github_response(payload: dict[str, object]) -> Mock:
    """AI-Generated.

    Return a minimal GitHub HTTP response double.
    """
    response = Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def test_github_login_start_sets_signed_state_and_safe_return(
    auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AI-Generated.

    Start OAuth login with signed cookies and a same-site return path.
    """
    monkeypatch.setattr(auth, "token_urlsafe", lambda _: "oauth-state")
    response = TestClient(create_app()).get(
        "/api/v1/auth/github/start?return_to=//evil", follow_redirects=False
    )
    assert response.status_code == 307
    assert "github.com/login/oauth/authorize" in response.headers["location"]
    assert response.cookies[settings.auth_state_cookie_name] == auth._signed_state(
        "oauth-state", "session-secret"
    )
    assert response.cookies[settings.auth_return_to_cookie_name].strip('"') == "/"


def test_github_callback_creates_session_cookie(
    auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """AI-Generated.

    Exchange a valid GitHub callback for a local session cookie.
    """
    store = AuthSessionStore(
        create_engine(f"sqlite+pysqlite:///{tmp_path / 'auth.sqlite3'}")
    )
    app = create_app()
    app.dependency_overrides[get_auth_session_store] = lambda: store
    monkeypatch.setattr(
        auth.requests,
        "post",
        Mock(return_value=_github_response({"access_token": "gh-token"})),
    )
    monkeypatch.setattr(
        auth.requests,
        "get",
        Mock(return_value=_github_response({"login": "jmsssc"})),
    )
    client = TestClient(app)
    client.cookies.set(
        settings.auth_state_cookie_name, auth._signed_state("state", "session-secret")
    )
    client.cookies.set(settings.auth_return_to_cookie_name, "/adapters")
    response = client.get(
        "/api/v1/auth/github/callback?code=abc&state=state",
        follow_redirects=False,
    )
    session = store.get_session(response.cookies[settings.auth_session_cookie_name])
    assert response.status_code == 307
    assert response.headers["location"] == "http://localhost:5173/adapters"
    assert session is not None
    assert session.github_login == "jmsssc"


def test_github_callback_rejects_invalid_state(auth_env: None) -> None:
    """AI-Generated.

    Reject callbacks whose state does not match the signed cookie.
    """
    client = TestClient(create_app())
    client.cookies.set(
        settings.auth_state_cookie_name, auth._signed_state("good", "session-secret")
    )
    response = client.get(
        "/api/v1/auth/github/callback?code=abc&state=bad",
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid OAuth state."
    assert settings.auth_session_cookie_name not in response.cookies


def test_github_payload_failures_raise_auth_error(
    auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AI-Generated.

    Reject GitHub token and user payloads that omit the required fields.
    """
    monkeypatch.setattr(auth.requests, "post", Mock(return_value=_github_response({})))
    monkeypatch.setattr(auth.requests, "get", Mock(return_value=_github_response({})))
    with pytest.raises(HTTPException) as token_error:
        auth._github_access_token("client-id", "client-secret", "code")
    with pytest.raises(HTTPException) as user_error:
        auth._github_user("gh-token")
    assert token_error.value.status_code == 400
    assert user_error.value.status_code == 400
    assert token_error.value.detail == "GitHub login failed."


def test_auth_me_and_logout_use_session_dependencies() -> None:
    """AI-Generated.

    Return the current user and delete the current browser session on logout.
    """
    app = create_app()
    store = Mock()
    app.dependency_overrides[get_auth_session_store] = lambda: store
    app.dependency_overrides[get_current_auth_session] = lambda: AuthSession(
        github_login="jmsssc"
    )
    client = TestClient(app)
    client.cookies.set(settings.auth_session_cookie_name, "session-token")
    me_response = client.get("/api/v1/auth/me")
    logout_response = client.post("/api/v1/auth/logout")
    assert me_response.json()["github_login"] == "jmsssc"
    assert logout_response.status_code == 204
    assert store.delete_session.call_args.args == ("session-token",)
