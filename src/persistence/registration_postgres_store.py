"""PostgreSQL registration store setup."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from src.persistence.registration_store_base import SQLAlchemyRegistrationStore
from src.persistence.schema import initialize_schema


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
        initialize_schema(self.engine)

    def _build_engine(self) -> Engine:
        return create_engine(
            self.database_url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            pool_recycle=3600,
            echo=False,
        )
