"""SQLAlchemy-backed PostgreSQL storage for adapter registration requests."""

from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from src.persistence.registration_store_base import SQLAlchemyRegistrationStore
from src.persistence.tables import metadata


class PostgreSQLRegistrationStore(SQLAlchemyRegistrationStore):
    """Persist registration requests in PostgreSQL through SQLAlchemy Core.

    This adapter is optimized for production use with PostgreSQL and includes
    connection pooling, automatic reconnection, and production-grade settings.
    """

    def __init__(self, database_url: str) -> None:
        """Create a store that reads and writes registrations to PostgreSQL.

        Args:
            database_url: PostgreSQL connection string, e.g.,
                         'postgresql://user:pass@localhost:5432/dbname'
                         or 'postgresql+psycopg2://user:pass@localhost:5432/dbname'
        """
        self.database_url = database_url
        self.engine = self._build_engine()
        self._initialize_database()

    def _initialize_database(self) -> None:
        """Create the schema if it does not exist."""
        metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            for column_name in (
                "description",
                "contact_email",
                "license_value",
                "doi",
                "submitted_by_github_login",
            ):
                connection.execute(
                    text(
                        "ALTER TABLE registration_sources "
                        f"ADD COLUMN IF NOT EXISTS {column_name} VARCHAR"
                    )
                )

    def _build_engine(self) -> Engine:
        """Create the SQLAlchemy engine for PostgreSQL with production settings."""
        return create_engine(
            self.database_url,
            pool_pre_ping=True,  # Verify connections before using
            pool_size=10,  # Connection pool size
            max_overflow=20,  # Additional connections under load
            pool_recycle=3600,  # Recycle connections after 1 hour
            echo=False,  # Set to True for SQL logging in development
        )
