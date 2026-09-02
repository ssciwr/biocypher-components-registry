"""Migrate legacy GitHub login columns to GitHub user id columns.

This helper was created by AI so we can smoothly transition now; better would have better creating a migration file or alembic migration
at the time of changing the property instead. This code does not try to back fill/replace values so running this will remove existing
logins/adapter registrations locally. The old github_login columns can still break inserts if they were NOT NULL and the login/user_id
column exists across a few different entities."""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from src.persistence.tables import adapter_endorsements_table, auth_sessions_table

AUTH_SESSIONS = "auth_sessions"
REGISTRATION_SOURCES = "registration_sources"
ADAPTER_ENDORSEMENTS = "adapter_endorsements"
GITHUB_LOGIN = "github_login"
SUBMITTED_BY_GITHUB_LOGIN = "submitted_by_github_login"


def migrate_auth_sessions_table(connection: Connection) -> None:
    if not _table_exists(connection, AUTH_SESSIONS):
        return

    columns = _table_columns(connection, AUTH_SESSIONS)
    if GITHUB_LOGIN not in columns:
        return

    _drop_table(connection, AUTH_SESSIONS)
    auth_sessions_table.create(connection, checkfirst=True)


def migrate_registration_github_login_columns(connection: Connection) -> None:
    _migrate_registration_sources(connection)
    _migrate_adapter_endorsements(connection)


def _migrate_registration_sources(connection: Connection) -> None:
    if not _table_exists(connection, REGISTRATION_SOURCES):
        return

    if SUBMITTED_BY_GITHUB_LOGIN in _table_columns(connection, REGISTRATION_SOURCES):
        _drop_column(connection, REGISTRATION_SOURCES, SUBMITTED_BY_GITHUB_LOGIN)


def _migrate_adapter_endorsements(connection: Connection) -> None:
    if not _table_exists(connection, ADAPTER_ENDORSEMENTS):
        return

    if GITHUB_LOGIN not in _table_columns(connection, ADAPTER_ENDORSEMENTS):
        return

    _drop_table(connection, ADAPTER_ENDORSEMENTS)
    adapter_endorsements_table.create(connection, checkfirst=True)


def _drop_column(
    connection: Connection,
    table_name: str,
    column_name: str,
) -> None:
    connection.execute(text(f"ALTER TABLE {table_name} DROP COLUMN {column_name}"))


def _drop_table(connection: Connection, table_name: str) -> None:
    connection.execute(text(f"DROP TABLE {table_name}"))


def _table_exists(connection: Connection, table_name: str) -> bool:
    return inspect(connection).has_table(table_name)


def _table_columns(connection: Connection, table_name: str) -> set[str]:
    return {
        str(column["name"]) for column in inspect(connection).get_columns(table_name)
    }
