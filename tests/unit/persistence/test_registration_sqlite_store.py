from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from src.core.adapter.service import create_registration_request
from src.core.registration.models import BatchRefreshSummary, RegistrationStatus
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore


def test_sqlite_store_creates_registration_table(tmp_path: Path) -> None:
    """Create the registration tables when the SQLite store is initialized."""
    database_path = tmp_path / "registry.sqlite3"

    SQLiteRegistrationStore(database_path)

    with sqlite3.connect(database_path) as connection:
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


def test_sqlite_store_persists_registration(tmp_path: Path) -> None:
    """Persist a registration request and return the stored record."""
    database_path = tmp_path / "registry.sqlite3"
    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    request = create_registration_request(
        adapter_name="Example Adapter",
        repository_location=str(repository),
        contact_email="maintainer@example.org",
    )
    store = SQLiteRegistrationStore(database_path)

    stored = store.create_registration(request)

    assert stored.status == RegistrationStatus.SUBMITTED
    assert stored.contact_email == "maintainer@example.org"
    with sqlite3.connect(database_path) as connection:
        source_row = connection.execute(
            """
            SELECT
                submitted_adapter_name,
                repository_location,
                source_kind,
                contact_email,
                is_active
            FROM registration_sources
            """
        ).fetchone()
        event_row = connection.execute(
            """
            SELECT source_id, event_type
            FROM registration_events
            """
        ).fetchone()

    assert source_row == (
        "Example Adapter",
        str(repository.resolve()),
        "local",
        "maintainer@example.org",
        1,
    )
    assert event_row is not None
    assert event_row[0] == stored.registration_id
    assert event_row[1] == "SUBMITTED"


def test_sqlite_store_builds_sqlalchemy_sqlite_engine(tmp_path: Path) -> None:
    """Create a SQLAlchemy engine that targets the configured SQLite database."""
    database_path = tmp_path / "registry.sqlite3"

    store = SQLiteRegistrationStore(database_path)

    assert store.engine.url.drivername == "sqlite+pysqlite"
    assert store.engine.url.database == str(database_path)


def test_sqlite_store_returns_registration_with_identifier_and_timestamp(
    tmp_path: Path,
) -> None:
    """Return generated metadata for the stored registration record."""
    database_path = tmp_path / "registry.sqlite3"
    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    request = create_registration_request(
        adapter_name="Example Adapter",
        repository_location=str(repository),
    )
    store = SQLiteRegistrationStore(database_path)

    stored = store.create_registration(request)

    assert stored.registration_id
    assert isinstance(datetime.fromisoformat(stored.created_at.isoformat()), datetime)


def test_sqlite_store_can_load_registration_by_identifier(tmp_path: Path) -> None:
    """Load a previously stored registration from the database."""
    database_path = tmp_path / "registry.sqlite3"
    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    request = create_registration_request(
        adapter_name="Example Adapter",
        repository_location=str(repository),
        contact_email="maintainer@example.org",
    )
    store = SQLiteRegistrationStore(database_path)
    created = store.create_registration(request)

    loaded = store.get_registration(created.registration_id)

    assert loaded is not None
    assert loaded.registration_id == created.registration_id
    assert loaded.status == RegistrationStatus.SUBMITTED
    assert loaded.contact_email == "maintainer@example.org"


def test_sqlite_store_lists_active_registrations_with_check_state(
    tmp_path: Path,
) -> None:
    """Return active registrations through the persistence port."""
    database_path = tmp_path / "registry.sqlite3"
    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    request = create_registration_request(
        adapter_name="Example Adapter",
        repository_location=str(repository),
    )
    store = SQLiteRegistrationStore(database_path)
    created = store.create_registration(request)

    store.mark_registration_valid(
        registration_id=created.registration_id,
        metadata={"@id": "example-adapter", "name": "Example Adapter", "version": "1.0.0"},
        metadata_path=str(repository / "croissant.jsonld"),
        profile_version="v1",
        uniqueness_key="example-adapter::1.0.0",
        observed_checksum="checksum-1",
    )

    registrations = store.list_active_registrations()

    assert len(registrations) == 1
    assert registrations[0].registration_id == created.registration_id
    assert registrations[0].status == RegistrationStatus.VALID
    assert registrations[0].last_checked_at is not None
    assert registrations[0].current_registry_entry_id is not None


def test_sqlite_store_marks_registration_valid(tmp_path: Path) -> None:
    """Persist approved metadata and mark a registration as valid."""
    database_path = tmp_path / "registry.sqlite3"
    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    request = create_registration_request(
        adapter_name="Example Adapter",
        repository_location=str(repository),
    )
    store = SQLiteRegistrationStore(database_path)
    created = store.create_registration(request)

    updated = store.mark_registration_valid(
        registration_id=created.registration_id,
        metadata={"@id": "example-adapter", "name": "Example Adapter", "version": "1.0.0"},
        metadata_path=str(repository / "croissant.jsonld"),
        profile_version="v1",
        uniqueness_key="example-adapter::1.0.0",
        observed_checksum="checksum-1",
    )

    assert updated.status == RegistrationStatus.VALID
    assert updated.metadata == {
        "@id": "example-adapter",
        "name": "Example Adapter",
        "version": "1.0.0",
    }
    assert updated.metadata_path == str(repository / "croissant.jsonld")
    assert updated.profile_version == "v1"
    assert updated.updated_at is not None
    assert updated.uniqueness_key == "example-adapter::1.0.0"

    with sqlite3.connect(database_path) as connection:
        entry_row = connection.execute(
            """
            SELECT source_id, adapter_name, adapter_version, uniqueness_key, is_active
            FROM registry_entries
            """
        ).fetchone()
        source_row = connection.execute(
            """
            SELECT current_registry_entry_id, updated_at
            FROM registration_sources
            WHERE id = ?
            """,
            (created.registration_id,),
        ).fetchone()
        event_row = connection.execute(
            """
            SELECT source_id, registry_entry_id, event_type, profile_version
            FROM registration_events
            WHERE source_id = ? AND event_type = 'VALID_CREATED'
            """,
            (created.registration_id,),
        ).fetchone()

    assert entry_row == (
        created.registration_id,
        "Example Adapter",
        "1.0.0",
        "example-adapter::1.0.0",
        1,
    )
    assert source_row is not None
    assert source_row[0]
    assert event_row is not None
    assert event_row[0] == created.registration_id
    assert event_row[2] == "VALID_CREATED"
    assert event_row[3] == "v1"
    assert source_row[1] is not None

    with sqlite3.connect(database_path) as connection:
        checksum_row = connection.execute(
            """
            SELECT metadata_checksum
            FROM registry_entries
            WHERE uniqueness_key = 'example-adapter::1.0.0'
            """
        ).fetchone()
        observed_checksum_row = connection.execute(
            """
            SELECT observed_checksum
            FROM registration_events
            WHERE source_id = ? AND event_type = 'VALID_CREATED'
            """,
            (created.registration_id,),
        ).fetchone()

    assert checksum_row == ("checksum-1",)
    assert observed_checksum_row == ("checksum-1",)


def test_sqlite_store_marks_registration_invalid_and_persists_errors(
    tmp_path: Path,
) -> None:
    """Persist failed validation details and mark a registration as invalid."""
    database_path = tmp_path / "registry.sqlite3"
    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    request = create_registration_request(
        adapter_name="Example Adapter",
        repository_location=str(repository),
    )
    store = SQLiteRegistrationStore(database_path)
    created = store.create_registration(request)

    updated = store.mark_registration_invalid(
        registration_id=created.registration_id,
        errors=["Missing required property: version"],
        profile_version="v1",
        metadata={"@id": "example-adapter", "name": "Example Adapter"},
        metadata_path=str(repository / "croissant.jsonld"),
        observed_checksum="checksum-invalid",
    )

    assert updated.status == RegistrationStatus.INVALID
    assert updated.validation_errors == ["Missing required property: version"]
    assert updated.profile_version == "v1"
    assert updated.metadata == {"@id": "example-adapter", "name": "Example Adapter"}

    with sqlite3.connect(database_path) as connection:
        event_row = connection.execute(
            """
            SELECT source_id, event_type, profile_version, error_details
            FROM registration_events
            WHERE source_id = ? AND event_type = 'INVALID_SCHEMA'
            """,
            (created.registration_id,),
        ).fetchone()

    assert event_row is not None
    assert event_row[0] == created.registration_id
    assert event_row[1] == "INVALID_SCHEMA"
    assert event_row[2] == "v1"
    assert "Missing required property: version" in event_row[3]

    with sqlite3.connect(database_path) as connection:
        observed_checksum_row = connection.execute(
            """
            SELECT observed_checksum
            FROM registration_events
            WHERE source_id = ? AND event_type = 'INVALID_SCHEMA'
            """,
            (created.registration_id,),
        ).fetchone()

    assert observed_checksum_row == ("checksum-invalid",)


def test_sqlite_store_lists_registration_events(tmp_path: Path) -> None:
    """Return registration event history through the persistence port."""
    database_path = tmp_path / "registry.sqlite3"
    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    request = create_registration_request(
        adapter_name="Example Adapter",
        repository_location=str(repository),
    )
    store = SQLiteRegistrationStore(database_path)
    created = store.create_registration(request)
    store.mark_registration_invalid(
        registration_id=created.registration_id,
        errors=["Missing required property: version"],
        profile_version="v1",
        metadata={"@id": "example-adapter", "name": "Example Adapter"},
        metadata_path=str(repository / "croissant.jsonld"),
        observed_checksum="checksum-invalid",
    )

    events = store.list_registration_events(created.registration_id)

    assert [event.event_type for event in events] == ["SUBMITTED", "INVALID_SCHEMA"]
    assert events[0].source_id == created.registration_id
    assert events[1].source_id == created.registration_id
    assert events[1].profile_version == "v1"
    assert events[1].error_details == ["Missing required property: version"]
    assert events[1].observed_checksum == "checksum-invalid"
    assert events[1].started_at <= events[1].finished_at


def test_sqlite_store_lists_active_registry_entries(tmp_path: Path) -> None:
    """Return canonical valid registry entries through the persistence port."""
    database_path = tmp_path / "registry.sqlite3"
    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    request = create_registration_request(
        adapter_name="Example Adapter",
        repository_location=str(repository),
    )
    store = SQLiteRegistrationStore(database_path)
    created = store.create_registration(request)
    store.mark_registration_valid(
        registration_id=created.registration_id,
        metadata={"@id": "example-adapter", "name": "Example Adapter", "version": "1.0.0"},
        metadata_path=str(repository / "croissant.jsonld"),
        profile_version="v1",
        uniqueness_key="example-adapter::1.0.0",
        observed_checksum="checksum-1",
    )

    entries = store.list_registry_entries()

    assert len(entries) == 1
    assert entries[0].source_id == created.registration_id
    assert entries[0].adapter_name == "Example Adapter"
    assert entries[0].adapter_version == "1.0.0"
    assert entries[0].profile_version == "v1"
    assert entries[0].uniqueness_key == "example-adapter::1.0.0"
    assert entries[0].metadata_checksum == "checksum-1"
    assert entries[0].metadata == {
        "@id": "example-adapter",
        "name": "Example Adapter",
        "version": "1.0.0",
    }
    assert entries[0].is_active is True


def test_sqlite_store_loads_registry_entry_by_identifier(tmp_path: Path) -> None:
    """Return one canonical valid registry entry through the persistence port."""
    database_path = tmp_path / "registry.sqlite3"
    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    request = create_registration_request(
        adapter_name="Example Adapter",
        repository_location=str(repository),
    )
    store = SQLiteRegistrationStore(database_path)
    created = store.create_registration(request)
    store.mark_registration_valid(
        registration_id=created.registration_id,
        metadata={"@id": "example-adapter", "name": "Example Adapter", "version": "1.0.0"},
        metadata_path=str(repository / "croissant.jsonld"),
        profile_version="v1",
        uniqueness_key="example-adapter::1.0.0",
        observed_checksum="checksum-1",
    )
    entry_id = store.list_registry_entries()[0].entry_id

    entry = store.get_registry_entry(entry_id)

    assert entry is not None
    assert entry.entry_id == entry_id
    assert entry.source_id == created.registration_id
    assert entry.adapter_name == "Example Adapter"
    assert entry.uniqueness_key == "example-adapter::1.0.0"
    assert entry.metadata == {
        "@id": "example-adapter",
        "name": "Example Adapter",
        "version": "1.0.0",
    }


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


def test_sqlite_store_get_registration_reconstructs_status_from_three_tables(
    tmp_path: Path,
) -> None:
    """Rebuild one registration from source, entry, and event history only."""
    database_path = tmp_path / "registry.sqlite3"
    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    request = create_registration_request(
        adapter_name="Example Adapter",
        repository_location=str(repository),
    )
    store = SQLiteRegistrationStore(database_path)
    created = store.create_registration(request)

    store.mark_registration_valid(
        registration_id=created.registration_id,
        metadata={"@id": "example-adapter", "name": "Example Adapter", "version": "1.0.0"},
        metadata_path=str(repository / "croissant.jsonld"),
        profile_version="v1",
        uniqueness_key="example-adapter::1.0.0",
        observed_checksum="checksum-1",
    )

    loaded = store.get_registration(created.registration_id)

    assert loaded is not None
    assert loaded.status == RegistrationStatus.VALID
    assert loaded.adapter_id == "example-adapter"
    assert loaded.uniqueness_key == "example-adapter::1.0.0"
