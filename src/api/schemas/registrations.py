"""Pydantic schemas for adapter registration API contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.core.registration.models import (
    RegistrationEvent,
    RegistrationStatus,
    StoredRegistration,
)


# ===========================================================
# =====================  OpenAPI Examples ===================
# ===========================================================


REGISTRATION_CREATE_EXAMPLE: dict[str, Any] = {
    "adapter_name": "Manual Example Adapter",
    "repository_location": "/tmp/biocypher-api-manual-adapter",
    "contact_email": "maintainer@example.org",
}


# ===========================================================
# =====================  Input Models =======================
# ===========================================================


class RegistrationCreateRequest(BaseModel):
    """Request body for creating an adapter registration."""

    model_config = ConfigDict(json_schema_extra={"example": REGISTRATION_CREATE_EXAMPLE})

    adapter_name: str = Field(
        ...,
        min_length=1,
        description="Human-readable adapter name supplied by the maintainer.",
    )
    repository_location: str = Field(
        ...,
        min_length=1,
        description=(
            "Local repository path or supported remote repository URL containing "
            "a root-level croissant.jsonld file."
        ),
    )
    contact_email: str | None = Field(
        default=None,
        description="Optional maintainer contact email for follow-up.",
    )

    @field_validator("adapter_name", "repository_location")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        """Normalize required text fields and reject blank values."""
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Field must not be blank.")
        return normalized_value

    @field_validator("contact_email")
    @classmethod
    def _normalize_contact_email(cls, value: str | None) -> str | None:
        """Normalize an optional contact email for API input."""
        if value is None:
            return None

        normalized_value = value.strip()
        if not normalized_value:
            return None

        local_part, separator, domain = normalized_value.partition("@")
        if not separator or not local_part or "." not in domain:
            raise ValueError("Contact email must be a valid email address.")

        return normalized_value


# ===========================================================
# =====================  Output Models ======================
# ===========================================================


class RegistrationCreateResponse(BaseModel):
    """Response returned after creating an adapter registration."""

    registration_id: str
    adapter_name: str
    adapter_id: str
    repository_location: str
    repository_kind: Literal["local", "remote"] | str
    status: RegistrationStatus
    created_at: datetime
    contact_email: str | None = None

    @classmethod
    def from_stored(cls, registration: StoredRegistration) -> "RegistrationCreateResponse":
        """Build an API response from a stored core registration model."""
        return cls(
            registration_id=registration.registration_id,
            adapter_name=registration.adapter_name,
            adapter_id=registration.adapter_id,
            repository_location=registration.repository_location,
            repository_kind=registration.repository_kind,
            status=registration.status,
            created_at=registration.created_at,
            contact_email=registration.contact_email,
        )


class RegistrationDetailResponse(RegistrationCreateResponse):
    """Detailed response for one stored registration."""

    metadata_path: str | None = None
    metadata: dict[str, Any] | None = None
    profile_version: str | None = None
    updated_at: datetime | None = None
    uniqueness_key: str | None = None
    validation_errors: list[str] | None = None

    @classmethod
    def from_stored(cls, registration: StoredRegistration) -> "RegistrationDetailResponse":
        """Build a detailed API response from a stored core registration model."""
        return cls(
            registration_id=registration.registration_id,
            adapter_name=registration.adapter_name,
            adapter_id=registration.adapter_id,
            repository_location=registration.repository_location,
            repository_kind=registration.repository_kind,
            status=registration.status,
            created_at=registration.created_at,
            contact_email=registration.contact_email,
            metadata_path=registration.metadata_path,
            metadata=registration.metadata,
            profile_version=registration.profile_version,
            updated_at=registration.updated_at,
            uniqueness_key=registration.uniqueness_key,
            validation_errors=registration.validation_errors,
        )


class RegistrationListItemResponse(RegistrationCreateResponse):
    """Summary response model for one registration in a list."""

    profile_version: str | None = None
    updated_at: datetime | None = None
    uniqueness_key: str | None = None

    @classmethod
    def from_stored(cls, registration: StoredRegistration) -> "RegistrationListItemResponse":
        """Build a list item response from a stored core registration model."""
        return cls(
            registration_id=registration.registration_id,
            adapter_name=registration.adapter_name,
            adapter_id=registration.adapter_id,
            repository_location=registration.repository_location,
            repository_kind=registration.repository_kind,
            status=registration.status,
            created_at=registration.created_at,
            contact_email=registration.contact_email,
            profile_version=registration.profile_version,
            updated_at=registration.updated_at,
            uniqueness_key=registration.uniqueness_key,
        )


class RegistrationListResponse(BaseModel):
    """Response model for a registration list."""

    items: list[RegistrationListItemResponse]


class RegistrationEventResponse(BaseModel):
    """Response model for one registration event."""

    event_id: str
    source_id: str
    registry_entry_id: str | None = None
    event_type: str
    message: str | None = None
    profile_version: str | None = None
    error_details: list[str] | None = None
    observed_checksum: str | None = None
    mlcroissant_valid: bool | None = None
    schema_valid: bool | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @classmethod
    def from_event(cls, event: RegistrationEvent) -> "RegistrationEventResponse":
        """Build an API response from a core registration event model."""
        return cls(
            event_id=event.event_id,
            source_id=event.source_id,
            registry_entry_id=event.registry_entry_id,
            event_type=event.event_type,
            message=event.message,
            profile_version=event.profile_version,
            error_details=event.error_details,
            observed_checksum=event.observed_checksum,
            mlcroissant_valid=event.mlcroissant_valid,
            schema_valid=event.schema_valid,
            started_at=event.started_at,
            finished_at=event.finished_at,
        )


class RegistrationEventListResponse(BaseModel):
    """Response model for a registration event history list."""

    items: list[RegistrationEventResponse]


class RegistrationProcessResponse(RegistrationDetailResponse):
    """Response returned after processing one registration."""


class RegistrationRevalidateResponse(RegistrationDetailResponse):
    """Response returned after revalidating one registration."""
