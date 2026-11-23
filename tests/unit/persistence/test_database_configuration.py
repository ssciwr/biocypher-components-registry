"""Host and container launchers select a database without inheriting each other."""

from pathlib import Path

import pytest
import yaml

from src.core.settings import DatabaseBackend, load_database_settings


def test_explicit_sqlite_backend_uses_configured_path(monkeypatch, tmp_path):
    path = tmp_path / "registry.sqlite3"
    monkeypatch.setenv("DATABASE_BACKEND", "sqlite")
    monkeypatch.setenv("SQLITE_DATABASE_PATH", str(path))
    configured = load_database_settings()
    assert configured.backend is DatabaseBackend.SQLITE
    assert configured.sqlite_database_path == path


def test_postgres_components_encode_password_and_database(monkeypatch):
    monkeypatch.setenv("DATABASE_BACKEND", "postgresql")
    monkeypatch.setenv("POSTGRES_HOST", "database")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_USER", "test-user")
    monkeypatch.setenv("POSTGRES_DB", "test/database")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p@ss:/?#%")
    configured = load_database_settings()
    url = configured.postgres_url
    assert configured.backend is DatabaseBackend.POSTGRESQL
    assert url is not None
    assert url.host == "database"
    assert url.password == "p@ss:/?#%"
    assert url.database == "test/database"


def test_invalid_backend_is_rejected(monkeypatch):
    monkeypatch.setenv("DATABASE_BACKEND", "mysql")
    try:
        load_database_settings()
    except ValueError as exc:
        message = str(exc)
        assert "sqlite" in message
        assert "postgresql" in message
    else:
        raise AssertionError("invalid backend must be rejected")


def test_missing_backend_is_rejected(monkeypatch):
    monkeypatch.delenv("DATABASE_BACKEND", raising=False)

    with pytest.raises(ValueError, match="DATABASE_BACKEND is required"):
        load_database_settings()


def test_sqlite_backend_requires_a_database_path(monkeypatch):
    monkeypatch.setenv("DATABASE_BACKEND", "sqlite")
    monkeypatch.delenv("SQLITE_DATABASE_PATH", raising=False)

    with pytest.raises(ValueError, match="SQLITE_DATABASE_PATH is required"):
        load_database_settings()


@pytest.mark.parametrize(
    ("port", "message"),
    [
        ("not-a-port", "POSTGRES_PORT must be an integer"),
        ("0", "POSTGRES_PORT must be between 1 and 65535"),
        ("65536", "POSTGRES_PORT must be between 1 and 65535"),
    ],
)
def test_postgres_backend_rejects_invalid_ports(monkeypatch, port, message):
    monkeypatch.setenv("DATABASE_BACKEND", "postgresql")
    monkeypatch.setenv("POSTGRES_PORT", port)

    with pytest.raises(ValueError, match=message):
        load_database_settings()


@pytest.mark.parametrize(
    "missing_name",
    ["POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_HOST", "POSTGRES_DB"],
)
def test_postgres_backend_requires_every_connection_component(
    monkeypatch, missing_name
):
    values = {
        "DATABASE_BACKEND": "postgresql",
        "POSTGRES_HOST": "database",
        "POSTGRES_PORT": "5432",
        "POSTGRES_USER": "registry",
        "POSTGRES_PASSWORD": "secret",
        "POSTGRES_DB": "registry",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv(missing_name)

    with pytest.raises(ValueError, match=rf"{missing_name} is required"):
        load_database_settings()


@pytest.mark.parametrize(
    "compose_file", ["docker-compose-sqlite.yml", "docker-compose-postgresql.yml"]
)
def test_compose_repository_policy_defaults_to_public_hosts(compose_file):
    root = Path(__file__).resolve().parents[3]
    compose = yaml.safe_load((root / compose_file).read_text())
    environment = compose["services"]["backend"]["environment"]
    # Compose's :- operator applies the default for both unset and empty values.
    assert environment["REGISTRY_ALLOWED_REPOSITORY_HOSTS"] == (
        "${REGISTRY_ALLOWED_REPOSITORY_HOSTS:-github.com,gitlab.com}"
    )


def test_compose_backends_override_host_database_configuration():
    root = Path(__file__).resolve().parents[3]
    sqlite = yaml.safe_load((root / "docker-compose-sqlite.yml").read_text())
    postgres = yaml.safe_load((root / "docker-compose-postgresql.yml").read_text())
    sqlite_environment = sqlite["services"]["backend"]["environment"]
    postgres_environment = postgres["services"]["backend"]["environment"]
    assert "env_file" not in sqlite["services"]["backend"]
    assert "env_file" not in postgres["services"]["backend"]
    assert sqlite_environment["DATABASE_BACKEND"] == "sqlite"
    assert sqlite_environment["SQLITE_DATABASE_PATH"] == "/app/data/registry.sqlite3"
    assert "POSTGRES_PASSWORD" not in sqlite_environment
    assert postgres_environment["DATABASE_BACKEND"] == "postgresql"
    assert postgres_environment["POSTGRES_HOST"] == "database"
    assert "SQLITE_DATABASE_PATH" not in postgres_environment
    assert sqlite["services"]["frontend"]["volumes"][0].startswith(
        "./frontend-placeholder:"
    )
    assert postgres["services"]["frontend"]["volumes"][0].startswith(
        "./frontend-placeholder:"
    )
