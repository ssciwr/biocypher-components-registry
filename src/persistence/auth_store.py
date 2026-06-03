"""Persistence for short-lived GitHub auth sessions."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from secrets import token_urlsafe

from sqlalchemy import delete, insert, select
from sqlalchemy.engine import Engine

from src.core.auth.models import AuthSession
from src.persistence.tables import auth_sessions_table, metadata


class AuthSessionStore:
    """Persist browser auth sessions without storing GitHub access tokens."""

    def __init__(self, engine: Engine) -> None:
        """Prepare the auth table for the configured database."""
        self.engine = engine
        self._initialize_database()

    def _initialize_database(self) -> None:
        metadata.create_all(self.engine)
        if self.engine.dialect.name != "sqlite":
            return

        with self.engine.begin() as connection:
            columns = {
                str(row["name"]): row
                for row in connection.exec_driver_sql(
                    "PRAGMA table_info(auth_sessions)"
                ).mappings()
            }
            expected_columns = {"id_hash", "github_login", "expires_at"}
            if set(columns) == expected_columns:
                return

            connection.exec_driver_sql("DROP TABLE IF EXISTS auth_sessions_new")
            connection.exec_driver_sql(
                """
                CREATE TABLE auth_sessions_new (
                    id_hash VARCHAR NOT NULL,
                    github_login VARCHAR NOT NULL,
                    expires_at VARCHAR NOT NULL,
                    PRIMARY KEY (id_hash)
                )
                """
            )
            if expected_columns.issubset(columns):
                connection.exec_driver_sql(
                    """
                    INSERT INTO auth_sessions_new (id_hash, github_login, expires_at)
                    SELECT id_hash, github_login, expires_at
                    FROM auth_sessions
                    WHERE github_login IS NOT NULL AND expires_at IS NOT NULL
                    """
                )
            connection.exec_driver_sql("DROP TABLE auth_sessions")
            connection.exec_driver_sql(
                "ALTER TABLE auth_sessions_new RENAME TO auth_sessions"
            )

    def create_session(
        self,
        *,
        github_login: str,
        expires_at: datetime,
    ) -> str:
        """Store a hashed session token and return the raw cookie token."""
        token = token_urlsafe(32)
        with self.engine.begin() as connection:
            connection.execute(
                insert(auth_sessions_table).values(
                    id_hash=_session_hash(token),
                    github_login=github_login,
                    expires_at=expires_at.isoformat(),
                )
            )
        return token

    def get_session(self, token: str) -> AuthSession | None:
        """Return a valid session for the raw cookie token."""
        with self.engine.connect() as connection:
            row = connection.execute(
                select(auth_sessions_table).where(
                    auth_sessions_table.c.id_hash == _session_hash(token)
                )
            ).mappings().first()

        if row is None:
            return None
        if datetime.fromisoformat(str(row["expires_at"])) <= datetime.now(UTC):
            return None
        return AuthSession(
            github_login=str(row["github_login"]),
        )

    def delete_session(self, token: str) -> None:
        """Remove one browser auth session."""
        with self.engine.begin() as connection:
            connection.execute(
                delete(auth_sessions_table).where(
                    auth_sessions_table.c.id_hash == _session_hash(token)
                )
            )


def _session_hash(token: str) -> str:
    """Hash the cookie token before persistence."""
    return sha256(token.encode("utf-8")).hexdigest()
