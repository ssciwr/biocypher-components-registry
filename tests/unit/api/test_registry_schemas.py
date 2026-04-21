from __future__ import annotations

from datetime import UTC, datetime

from src.api.schemas.registry import (
    RegistryEntryResponse,
    RegistryRefreshLatestResponse,
    RegistryRefreshResponse,
    RegistryRegistrationResponse,
)
from src.core.registration.models import (
    BatchRefreshRecord,
    BatchRefreshSummary,
    RegistrationStatus,
    RegistryEntry,
    StoredRegistration,
)


# ===========================================================
# Registry Schema Tests
# ===========================================================


def test_registry_refresh_response_maps_from_batch_summary() -> None:
    """Build the registry refresh response from the core summary model."""
    summary = BatchRefreshSummary(
        active_sources=3,
        processed=3,
        valid_created=1,
        unchanged=0,
        invalid=1,
        duplicate=0,
        rejected_same_version_changed=0,
        fetch_failed=1,
    )

    response = RegistryRefreshResponse.from_summary(summary)

    assert response.active_sources == 3
    assert response.processed == 3
    assert response.valid_created == 1
    assert response.invalid == 1
    assert response.fetch_failed == 1


def test_registry_refresh_latest_response_maps_from_refresh_record() -> None:
    """Build the latest refresh response from the core refresh record."""
    started_at = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)
    finished_at = datetime(2026, 4, 16, 12, 1, tzinfo=UTC)
    record = BatchRefreshRecord(
        refresh_id="refresh-1",
        started_at=started_at,
        finished_at=finished_at,
        active_sources=3,
        processed=3,
        valid_created=1,
        invalid=1,
        fetch_failed=1,
    )

    response = RegistryRefreshLatestResponse.from_record(record)

    assert response.refresh_id == "refresh-1"
    assert response.started_at == started_at
    assert response.finished_at == finished_at
    assert response.active_sources == 3
    assert response.valid_created == 1
    assert response.invalid == 1
    assert response.fetch_failed == 1


def test_registry_source_row_response_maps_from_registration() -> None:
    """Build a registry registration row from a stored registration."""
    created_at = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)
    updated_at = datetime(2026, 4, 16, 12, 5, tzinfo=UTC)
    registration = StoredRegistration(
        registration_id="reg-1",
        adapter_name="Example Adapter",
        adapter_id="example-adapter",
        repository_location="https://github.com/example/example-adapter",
        repository_kind="remote",
        status=RegistrationStatus.VALID,
        created_at=created_at,
        contact_email="maintainer@example.org",
        profile_version="v1",
        updated_at=updated_at,
        uniqueness_key="example-adapter::1.0.0",
    )

    response = RegistryRegistrationResponse.from_registration(
        registration,
        latest_event_type="VALID_CREATED",
    )

    assert response.registration_id == "reg-1"
    assert response.adapter_name == "Example Adapter"
    assert response.status == RegistrationStatus.VALID
    assert response.latest_event_type == "VALID_CREATED"
    assert response.profile_version == "v1"
    assert response.uniqueness_key == "example-adapter::1.0.0"


def test_registry_entry_response_maps_from_registry_entry() -> None:
    """Build a registry entry response from the core entry model."""
    created_at = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)
    updated_at = datetime(2026, 4, 16, 12, 5, tzinfo=UTC)
    entry = RegistryEntry(
        entry_id="entry-1",
        source_id="reg-1",
        adapter_name="Example Adapter",
        adapter_version="1.0.0",
        profile_version="v1",
        uniqueness_key="example-adapter::1.0.0",
        metadata_checksum="checksum-1",
        created_at=created_at,
        updated_at=updated_at,
        is_active=True,
    )

    response = RegistryEntryResponse.from_entry(entry)

    assert response.entry_id == "entry-1"
    assert response.source_id == "reg-1"
    assert response.adapter_name == "Example Adapter"
    assert response.adapter_version == "1.0.0"
    assert response.profile_version == "v1"
    assert response.uniqueness_key == "example-adapter::1.0.0"
    assert response.metadata_checksum == "checksum-1"
    assert response.created_at == created_at
    assert response.updated_at == updated_at
    assert response.is_active is True
