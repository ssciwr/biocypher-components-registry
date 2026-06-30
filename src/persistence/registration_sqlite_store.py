"""SQLite registration store setup."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from src.persistence.sqlalchemy_registration_store import SQLAlchemyRegistrationStore
from src.persistence.tables import metadata


class SQLiteRegistrationStore(SQLAlchemyRegistrationStore):
    """SQLite engine and migration wrapper for tests and local development.
    """

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = self._build_engine()
        self._initialize_database()

    def _initialize_database(self) -> None:
        metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            self._ensure_registration_sources_columns(connection)
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "uq_registration_source_repository_location "
                    "ON registration_sources (repository_location)"
                )
            )
            connection.execute(text("DROP INDEX IF EXISTS ix_registrations_uniqueness_key"))
            connection.execute(text("DROP TABLE IF EXISTS registration_failures"))
            connection.execute(text("DROP TABLE IF EXISTS registrations"))

    def _build_engine(self) -> Engine:
        return create_engine(f"sqlite+pysqlite:///{self.database_path}")

    def _ensure_registration_sources_columns(self, connection: Engine | object) -> None:
        columns = {
            str(row["name"])
            for row in connection.execute(
                text("PRAGMA table_info(registration_sources)")
            ).mappings()
        }
        for column_name in (
            "contact_email",
            "license_value",
            "doi",
            "cff_url",
            "submitted_by_github_login",
        ):
            if column_name not in columns:
                connection.execute(
                    text(
                        "ALTER TABLE registration_sources "
                        f"ADD COLUMN {column_name} VARCHAR"
                    )
                )
