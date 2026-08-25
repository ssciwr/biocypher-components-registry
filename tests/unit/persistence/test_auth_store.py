from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine

from src.persistence.auth_store import AuthSessionStore


def _auth_store(tmp_path: Path) -> AuthSessionStore:
    """AI-Generated.

    Create an isolated SQLite auth store for persistence tests.
    """
    return AuthSessionStore(
        create_engine(f"sqlite+pysqlite:///{tmp_path / 'auth.sqlite3'}")
    )


def test_auth_session_store_creates_reads_and_deletes_session(tmp_path: Path) -> None:
    """AI-Generated.

    Persist a short-lived auth session and delete it by raw token.
    """
    store = _auth_store(tmp_path)
    token = store.create_session(
        github_user_id="12345",
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    session = store.get_session(token)
    store.delete_session(token)
    assert token
    assert session is not None
    assert session.github_user_id == "12345"
    assert store.get_session(token) is None


def test_auth_session_store_ignores_missing_and_expired_sessions(
    tmp_path: Path,
) -> None:
    """AI-Generated.

    Treat unknown and expired browser session tokens as anonymous users.
    """
    store = _auth_store(tmp_path)
    token = store.create_session(
        github_user_id="12345",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    missing = store.get_session("missing-token")
    expired = store.get_session(token)
    assert missing is None
    assert expired is None
    assert token != "missing-token"
