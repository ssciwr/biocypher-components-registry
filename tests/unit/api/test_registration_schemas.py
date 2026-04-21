from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.api.schemas.registrations import (
    RegistrationCreateRequest,
    RegistrationCreateResponse,
    RegistrationDetailResponse,
    RegistrationEventResponse,
)
from src.core.registration.models import (
    RegistrationEvent,
    RegistrationStatus,
    StoredRegistration,
)


# ===========================================================
# Registration Schema Tests
# ===========================================================


def test_registration_create_request_normalizes_input_fields() -> None:
    """Normalize registration create input while keeping the API contract explicit."""
    request = RegistrationCreateRequest(
        adapter_name="  Example Adapter  ",
        repository_location="  https://github.com/example/example-adapter  ",
        contact_email="  maintainer@example.org  ",
    )

    assert request.adapter_name == "Example Adapter"
    assert request.repository_location == "https://github.com/example/example-adapter"
    assert request.contact_email == "maintainer@example.org"


def test_registration_create_request_treats_blank_contact_email_as_missing() -> None:
    """Allow omitted maintainer contact by normalizing blank contact email to None."""
    request = RegistrationCreateRequest(
        adapter_name="Example Adapter",
        repository_location="https://github.com/example/example-adapter",
        contact_email="   ",
    )

    assert request.contact_email is None


def test_registration_create_request_rejects_blank_required_fields() -> None:
    """Reject blank required registration create fields."""
    with pytest.raises(ValidationError):
        RegistrationCreateRequest(
            adapter_name="   ",
            repository_location="https://github.com/example/example-adapter",
        )


def test_registration_create_request_rejects_invalid_contact_email() -> None:
    """Reject invalid contact email values at the API boundary."""
    with pytest.raises(ValidationError, match="Contact email must be a valid email address."):
        RegistrationCreateRequest(
            adapter_name="Example Adapter",
            repository_location="https://github.com/example/example-adapter",
            contact_email="not-an-email",
        )


def test_registration_create_response_maps_from_stored_registration() -> None:
    """Build the create response from the core stored registration model."""
    created_at = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)
    registration = StoredRegistration(
        registration_id="reg-1",
        adapter_name="Example Adapter",
        adapter_id="example-adapter",
        repository_location="https://github.com/example/example-adapter",
        repository_kind="remote",
        status=RegistrationStatus.SUBMITTED,
        created_at=created_at,
        contact_email="maintainer@example.org",
    )

    response = RegistrationCreateResponse.from_stored(registration)

    assert response.registration_id == "reg-1"
    assert response.adapter_name == "Example Adapter"
    assert response.status == RegistrationStatus.SUBMITTED
    assert response.created_at == created_at
    assert response.contact_email == "maintainer@example.org"


def test_registration_detail_response_maps_optional_registration_fields() -> None:
    """Build the detail response from all relevant stored registration fields."""
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
        metadata_path="croissant.jsonld",
        metadata={"name": "Example Adapter"},
        profile_version="v1",
        updated_at=updated_at,
        uniqueness_key="example-adapter::1.0.0",
        validation_errors=[],
    )

    response = RegistrationDetailResponse.from_stored(registration)

    assert response.metadata_path == "croissant.jsonld"
    assert response.metadata == {"name": "Example Adapter"}
    assert response.profile_version == "v1"
    assert response.updated_at == updated_at
    assert response.uniqueness_key == "example-adapter::1.0.0"
    assert response.validation_errors == []


def test_registration_event_response_maps_from_registration_event() -> None:
    """Build an event response from the core registration event model."""
    started_at = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)
    finished_at = datetime(2026, 4, 16, 12, 1, tzinfo=UTC)
    event = RegistrationEvent(
        event_id="event-1",
        source_id="reg-1",
        registry_entry_id=None,
        event_type="FETCH_FAILED",
        message="Registration fetch/discovery failed.",
        profile_version=None,
        error_details=["croissant.jsonld not found"],
        observed_checksum=None,
        mlcroissant_valid=None,
        schema_valid=None,
        started_at=started_at,
        finished_at=finished_at,
    )

    response = RegistrationEventResponse.from_event(event)

    assert response.event_id == "event-1"
    assert response.source_id == "reg-1"
    assert response.event_type == "FETCH_FAILED"
    assert response.message == "Registration fetch/discovery failed."
    assert response.error_details == ["croissant.jsonld not found"]
    assert response.started_at == started_at
    assert response.finished_at == finished_at
