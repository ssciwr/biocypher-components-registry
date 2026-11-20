from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from src.core.registration.models import BatchRefreshSummary
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore
from tests.support.registration_fixtures import accepted_source, historical_source


def test_sqlite_store_creates_registration_table(tmp_path: Path) -> None:
    """Create the registration tables when the SQLite store is initialized."""
    database_path = tmp_path / "registry.sqlite3"

    SQLiteRegistrationStore(database_path)

    with closing(sqlite3.connect(database_path)) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert "registration_sources" in tables
    assert "registry_entries" in tables
    assert "registration_events" in tables
    assert "registry_refreshes" in tables
    assert "registrations" not in tables
    assert "registration_failures" not in tables


def test_sqlite_store_builds_sqlalchemy_sqlite_engine(tmp_path: Path) -> None:
    """Create a SQLAlchemy engine that targets the configured SQLite database."""
    database_path = tmp_path / "registry.sqlite3"

    store = SQLiteRegistrationStore(database_path)

    assert store.engine.url.drivername == "sqlite+pysqlite"
    assert store.engine.url.database == str(database_path)


def test_sqlite_store_returns_none_for_unknown_registry_entry(tmp_path: Path) -> None:
    """Return None when a canonical registry entry is unknown."""
    database_path = tmp_path / "registry.sqlite3"
    store = SQLiteRegistrationStore(database_path)

    entry = store.get_registry_entry("missing-entry")

    assert entry is None


def test_sqlite_store_records_and_loads_latest_batch_refresh(tmp_path: Path) -> None:
    """Persist and load the latest batch refresh summary through the port."""
    database_path = tmp_path / "registry.sqlite3"
    store = SQLiteRegistrationStore(database_path)
    older = store.record_batch_refresh(
        BatchRefreshSummary(active_sources=1, processed=1, valid_created=1),
        started_at=datetime(2026, 4, 16, 12, 0, tzinfo=UTC),
        finished_at=datetime(2026, 4, 16, 12, 1, tzinfo=UTC),
    )
    newer = store.record_batch_refresh(
        BatchRefreshSummary(active_sources=2, processed=2, invalid=1, fetch_failed=1),
        started_at=datetime(2026, 4, 16, 13, 0, tzinfo=UTC),
        finished_at=datetime(2026, 4, 16, 13, 1, tzinfo=UTC),
    )

    latest = store.get_latest_batch_refresh()

    assert older.refresh_id != newer.refresh_id
    assert latest is not None
    assert latest.refresh_id == newer.refresh_id
    assert latest.active_sources == 2
    assert latest.processed == 2
    assert latest.invalid == 1
    assert latest.fetch_failed == 1


def test_sqlite_store_returns_none_without_batch_refresh(tmp_path: Path) -> None:
    """Return None when no batch refresh has been persisted."""
    database_path = tmp_path / "registry.sqlite3"
    store = SQLiteRegistrationStore(database_path)

    assert store.get_latest_batch_refresh() is None


def test_atomic_acceptance_persists_source_metadata_and_event(tmp_path):
    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    stored = accepted_source(
        store,
        "https://github.com/owner/repo",
        owner="456",
        license_value="MIT",
        doi="10.1/example",
    )
    assert stored.registration_id and stored.created_at
    assert stored.submitted_by_github_user_id == "456"
    assert stored.license_value == "MIT" and stored.doi == "10.1/example"
    assert not hasattr(stored, "status")
    loaded = store.get_registration(stored.registration_id)
    assert loaded == stored
    assert store.get_registration("missing") is None
    assert (
        store.get_registration_by_repository_location("https://github.com/owner/repo")
        == stored
    )
    entries = store.list_registry_entries()
    assert len(entries) == 1
    assert entries[0].source_id == stored.registration_id
    assert entries[0].adapter_version == "1.0.0"
    assert entries[0].metadata_checksum
    assert store.get_registry_entry(entries[0].entry_id) == entries[0]
    events = store.list_registration_events(stored.registration_id)
    assert len(events) == 1 and events[0].event_type == "VALID_CREATED"
    assert events[0].registry_entry_id == entries[0].entry_id
    assert events[0].observed_checksum == entries[0].metadata_checksum


def test_failed_published_update_preserves_accepted_state_and_records_diagnostics(
    tmp_path,
):
    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    original = accepted_source(store, "https://github.com/owner/repo")
    store.record_update_failure(
        original.registration_id,
        "INVALID_SCHEMA",
        ["Missing license"],
        "Metadata rejected",
        datetime.now(UTC),
    )
    after = store.get_registration(original.registration_id)
    assert after.metadata == original.metadata
    assert after.current_registry_entry_id == original.current_registry_entry_id
    assert after.last_checked_at is not None
    assert not hasattr(after, "status")
    event = store.list_registration_events(original.registration_id)[-1]
    assert event.event_type == "INVALID_SCHEMA"
    assert event.error_details == ["Missing license"]


def test_unpublished_historical_sources_are_lookup_only(tmp_path):
    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    historical = historical_source(store, "https://github.com/owner/old")
    published = accepted_source(store, "https://github.com/owner/new")
    assert (
        store.get_registration(historical.registration_id).current_registry_entry_id
        is None
    )
    assert store.list_active_registration_ids() == [published.registration_id]
    assert [item.registration_id for item in store.list_active_registrations()] == [
        published.registration_id
    ]
    assert store.list_registration_events(historical.registration_id) == []


def test_non_unique_integrity_failure_is_not_reported_as_concurrency(tmp_path):
    import pytest
    from sqlalchemy.exc import IntegrityError

    store = SQLiteRegistrationStore(tmp_path / "broken.sqlite3")
    with store.engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TRIGGER reject_entry BEFORE INSERT ON registry_entries "
            "BEGIN SELECT RAISE(ABORT, 'test integrity violation'); END"
        )
    with pytest.raises(IntegrityError):
        accepted_source(store, "https://github.com/owner/rejected")
    assert (
        store.get_registration_by_repository_location(
            "https://github.com/owner/rejected"
        )
        is None
    )
    assert store.list_registry_entries() == []


def test_unique_insert_conflict_still_reports_concurrent_registration(
    tmp_path, monkeypatch
):
    import pytest

    from src.core.registration.errors import DuplicateRegistrationError

    store = SQLiteRegistrationStore(tmp_path / "race.sqlite3")
    accepted_source(store, "https://github.com/owner/first")
    # Simulate a competing insert becoming visible after the preflight lookup.
    monkeypatch.setattr(store, "_registry_entry_by_uniqueness_key", lambda *args: None)
    with pytest.raises(DuplicateRegistrationError, match="concurrently"):
        accepted_source(store, "https://github.com/owner/second")
    assert (
        store.get_registration_by_repository_location("https://github.com/owner/second")
        is None
    )
    assert len(store.list_registry_entries()) == 1
