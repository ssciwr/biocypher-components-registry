"""Create the current schema for a fresh database; no legacy upgrades."""

from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.persistence.tables import metadata


def initialize_schema(engine: Engine) -> None:
    """Serialize concurrent process startup while creating missing tables."""
    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_xact_lock(1111708161)"))
        elif engine.dialect.name == "sqlite":
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        metadata.create_all(connection)
