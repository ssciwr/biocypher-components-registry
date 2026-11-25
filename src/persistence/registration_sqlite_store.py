"""SQLite registration store setup."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

from src.persistence.registration_store_base import SQLAlchemyRegistrationStore
from src.persistence.schema import initialize_schema


class SQLiteRegistrationStore(SQLAlchemyRegistrationStore):
    """SQLite engine for the current registry schema."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = self._build_engine()
        self._initialize_database()

    def _initialize_database(self) -> None:
        initialize_schema(self.engine)

    def _build_engine(self) -> Engine:
        return create_engine(
            f"sqlite+pysqlite:///{self.database_path}",
            poolclass=NullPool,
        )  # Fix open sqlite handles (connections) bug seen in CI testing environment
