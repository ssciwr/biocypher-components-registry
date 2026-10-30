"""Fresh Docker PostgreSQL startup must not lock normal registry writes."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy.engine import make_url

from src.persistence.registration_postgres_store import PostgreSQLRegistrationStore


def test_reopening_current_schema_does_not_require_exclusive_table_locks(
    postgres_schema_url,
):
    store = PostgreSQLRegistrationStore(postgres_schema_url)
    url = make_url(postgres_schema_url)
    options = url.query["options"] + " -clock_timeout=500ms"
    reopening_url = url.update_query_dict({"options": options}).render_as_string(
        hide_password=False
    )
    try:
        with store.engine.begin() as writer:
            writer.exec_driver_sql(
                "LOCK TABLE registration_sources, registry_entries IN ROW EXCLUSIVE MODE"
            )
            reopened = PostgreSQLRegistrationStore(reopening_url)
            reopened.engine.dispose()
    finally:
        store.engine.dispose()


def test_concurrent_fresh_schema_initialization_succeeds(postgres_schema_url):
    barrier = Barrier(4)

    def initialize(_):
        barrier.wait(timeout=5)
        store = PostgreSQLRegistrationStore(postgres_schema_url)
        try:
            assert store.list_registry_entries() == []
        finally:
            store.engine.dispose()

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(initialize, range(4)))


def test_cli_preflight_checks_connection_without_creating_tables(
    postgres_schema_url, monkeypatch
):
    from sqlalchemy import create_engine, inspect

    from src.persistence.factory import check_database_connection

    monkeypatch.setenv("DATABASE_URL", postgres_schema_url)
    assert check_database_connection().startswith("PostgreSQL")
    engine = create_engine(postgres_schema_url)
    try:
        assert inspect(engine).get_table_names() == []
    finally:
        engine.dispose()
