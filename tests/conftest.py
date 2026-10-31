"""Keep ordinary tests independent of the developer's application configuration."""

import os

import pytest


def pytest_configure():
    # Applies before collection: test modules may import CLI entry points.
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"


@pytest.fixture(autouse=True)
def isolated_application_environment(monkeypatch, tmp_path):
    from src.persistence.factory import close_stores

    close_stores()
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_HOST", raising=False)
    monkeypatch.delenv("REGISTRY_ALLOWED_REPOSITORY_HOSTS", raising=False)
    monkeypatch.setenv("BIOCYPHER_REGISTRY_DB_PATH", str(tmp_path / "registry.sqlite3"))
    for name in (
        "GITHUB_OAUTH_CLIENT_ID",
        "GITHUB_OAUTH_CLIENT_SECRET",
        "AUTH_SESSION_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)
    yield
    close_stores()


@pytest.fixture(scope="session")
def postgres_test_url():
    from tests.support.postgres import PostgresTestUnavailable, docker_postgres_url

    container = os.environ.get("REGISTRY_TEST_POSTGRES_CONTAINER", "").strip()
    if not container:
        pytest.skip(
            "Start docker-compose.test.yml and set REGISTRY_TEST_POSTGRES_CONTAINER "
            "to exercise Docker PostgreSQL."
        )
    try:
        return docker_postgres_url(container)
    except PostgresTestUnavailable as exc:
        pytest.skip(str(exc))


@pytest.fixture
def postgres_schema_url(postgres_test_url):
    from uuid import uuid4

    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    schema = f"registry_test_{uuid4().hex}"
    admin = create_engine(postgres_test_url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        yield (
            make_url(postgres_test_url)
            .update_query_dict({"options": f"-csearch_path={schema}"})
            .render_as_string(hide_password=False)
        )
    finally:
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture(params=["sqlite", "postgres"])
def registration_store(tmp_path, request):
    from src.persistence.registration_postgres_store import PostgreSQLRegistrationStore
    from src.persistence.registration_sqlite_store import SQLiteRegistrationStore

    if request.param == "sqlite":
        store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    else:
        store = PostgreSQLRegistrationStore(
            request.getfixturevalue("postgres_schema_url")
        )
    try:
        yield store
    finally:
        store.engine.dispose()
