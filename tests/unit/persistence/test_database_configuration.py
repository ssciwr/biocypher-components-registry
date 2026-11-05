"""Host and container launchers select a database without inheriting each other."""

from pathlib import Path

import yaml
from sqlalchemy.engine import make_url

from src.core.settings import get_database_url


def test_blank_database_url_selects_sqlite(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "  ")
    assert get_database_url() is None


def test_postgres_components_encode_password_and_database(monkeypatch):
    monkeypatch.setenv("POSTGRES_HOST", "database")
    monkeypatch.setenv("POSTGRES_USER", "test-user")
    monkeypatch.setenv("POSTGRES_DB", "test/database")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p@ss:/?#%")
    url = make_url(get_database_url())
    assert url.host == "database"
    assert url.password == "p@ss:/?#%"
    assert url.database == "test/database"


def test_explicit_database_url_selects_host_configuration(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://user:password@localhost:5432/registry"
    )
    monkeypatch.setenv("POSTGRES_HOST", "database")
    assert make_url(get_database_url()).host == "localhost"


def test_compose_backends_override_host_database_configuration():
    root = Path(__file__).resolve().parents[3]
    sqlite = yaml.safe_load((root / "docker-compose-sqlite.yml").read_text())
    postgres = yaml.safe_load((root / "docker-compose-postgresql.yml").read_text())
    sqlite_environment = sqlite["services"]["backend"]["environment"]
    postgres_environment = postgres["services"]["backend"]["environment"]
    assert (
        sqlite_environment["DATABASE_URL"] == sqlite_environment["POSTGRES_HOST"] == ""
    )
    assert postgres_environment["DATABASE_URL"] == ""
    assert postgres_environment["POSTGRES_HOST"] == "database"
