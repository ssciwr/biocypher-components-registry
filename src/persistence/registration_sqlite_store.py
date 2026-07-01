"""SQLAlchemy-backed SQLite storage for adapter registration requests."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

from src.persistence.registration_store_base import SQLAlchemyRegistrationStore
from src.persistence.tables import metadata


class SQLiteRegistrationStore(SQLAlchemyRegistrationStore):
    """Persist registration requests in SQLite through SQLAlchemy Core."""

    def __init__(self, database_path: str | Path) -> None:
        """Create a store that reads and writes registrations to SQLite."""
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = self._build_engine()
        self._initialize_database()

    def _initialize_database(self) -> None:
        """Create the schema, apply lightweight migrations, and remove legacy tables."""
        metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            self._ensure_registration_sources_columns(connection)
            connection.execute(text("DROP INDEX IF EXISTS ix_registrations_uniqueness_key"))
            connection.execute(text("DROP TABLE IF EXISTS registration_failures"))
            connection.execute(text("DROP TABLE IF EXISTS registrations"))

    def _build_engine(self) -> Engine:
        """Create the SQLAlchemy engine for the configured SQLite database."""
        return create_engine(f"sqlite+pysqlite:///{self.database_path}", poolclass=NullPool)

    def _ensure_registration_sources_columns(self, connection: Engine | object) -> None:
        """Add missing registration source columns for existing SQLite databases."""
        columns = {
            str(row["name"])
            for row in connection.execute(
                text("PRAGMA table_info(registration_sources)")
            ).mappings()
        }
        if "contact_email" not in columns:
            connection.execute(
                text("ALTER TABLE registration_sources ADD COLUMN contact_email VARCHAR")
            )
