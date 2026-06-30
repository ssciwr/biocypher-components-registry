"""PostgreSQL registration store setup."""

from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from src.persistence.sqlalchemy_registration_store import SQLAlchemyRegistrationStore
from src.persistence.tables import metadata


class PostgreSQLRegistrationStore(SQLAlchemyRegistrationStore):
    """
    PostgreSQL engine and migration wrapper for the shared store.
    """

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.engine = self._build_engine()
        self._initialize_database()

    def _initialize_database(self) -> None:
        metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            for column_name in (
                "license_value",
                "doi",
                "cff_url",
                "submitted_by_github_login",
            ):
                connection.execute(
                    text(
                        "ALTER TABLE registration_sources "
                        f"ADD COLUMN IF NOT EXISTS {column_name} VARCHAR"
                    )
                )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "uq_registration_source_repository_location "
                    "ON registration_sources (repository_location)"
                )
            )

    def _build_engine(self) -> Engine:
        return create_engine(
            self.database_url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            pool_recycle=3600,
            echo=False,
        )
