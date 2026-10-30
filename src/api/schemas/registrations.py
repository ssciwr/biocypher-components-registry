"""Pydantic schemas for adapter registration API contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.core.registration.models import (
    AttemptStatus,
    ProcessingOutcome,
    RegistrationEvent,
    StoredRegistration,
)
from src.core.validation.results import CheckStatus

REGISTRATION_CREATE_EXAMPLE: dict[str, Any] = {
    "repository_location": "https://gitlab.example.org/biocypher/collectri",
    "license_value": "MIT",
    "doi": "10.5281/zenodo.1234567",
    "cff_url": "https://gitlab.example.org/biocypher/collectri/-/raw/main/CITATION.cff",
}


class ValidationDetailResponse(BaseModel):
    """Response-only context supplied by a metadata validator."""

    model_config = ConfigDict(from_attributes=True)

    message: str
    json_path: str | None = None
    requirement: str | None = None
    expected_format: str | None = None
    location_description: str | None = None
    source_file: str | None = None
    source_url: str | None = None
    line: int | None = Field(default=None, ge=1)
    column: int | None = Field(default=None, ge=1)
    location_kind: Literal["value", "containing_object"] | None = None


class ValidationCheckResponse(BaseModel):
    """A validation stage, its provenance, and its inline diagnostic information."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    status: CheckStatus
    description: str | None = None
    reason: str | None = None
    errors: list[str] = Field(default_factory=list)
    validation_details: list[ValidationDetailResponse] = Field(default_factory=list)
    parent_id: str | None = None
    dataset_index: int | None = None
    dataset_name: str | None = None
    profile_version: str | None = None
    schema_title: str | None = None
    schema_id: str | None = None
    schema_dialect: str | None = None
    validator_name: str | None = None
    validator_version: str | None = None


class RegistrationAttemptResponse(BaseModel):
    """One terminal attempt, with accepted state kept separate from errors."""

    attempt_status: AttemptStatus
    registration_id: str | None = None
    adapter_id: str | None = None
    adapter_name: str | None = None
    repository_location: str | None = None
    published_version: str | None = None
    update_applied: bool = False
    reason_code: str | None = None
    message: str
    validation_errors: list[str] = Field(default_factory=list)
    validation_details: list[ValidationDetailResponse] = Field(default_factory=list)
    validation_checks: list[ValidationCheckResponse] = Field(default_factory=list)
    profile_version: str | None = None

    @classmethod
    def from_outcome(cls, outcome: ProcessingOutcome) -> RegistrationAttemptResponse:
        registration = outcome.registration
        return cls(
            attempt_status=outcome.attempt_status,
            registration_id=registration.registration_id if registration else None,
            adapter_id=registration.adapter_id if registration else None,
            adapter_name=registration.adapter_name if registration else None,
            repository_location=registration.repository_location
            if registration
            else None,
            published_version=outcome.published_version,
            update_applied=outcome.update_applied,
            reason_code=outcome.reason_code,
            message=outcome.message,
            validation_errors=list(outcome.validation_errors),
            validation_details=[
                ValidationDetailResponse.model_validate(detail)
                for detail in outcome.validation_details
            ],
            validation_checks=[
                ValidationCheckResponse.model_validate(check)
                for check in outcome.validation_checks
            ],
            profile_version=outcome.profile_version,
        )


class RegistrationStreamEvent(BaseModel):
    """SSE data envelope; exactly one terminal result or error ends a stream."""

    type: Literal["snapshot", "check", "result", "error"]
    checks: list[ValidationCheckResponse] = Field(default_factory=list)
    check: ValidationCheckResponse | None = None
    result: RegistrationAttemptResponse | None = None
    status_code: int | None = None
    detail: str | None = None


class RegistrationCreateRequest(BaseModel):
    """Request body for creating an adapter registration."""

    model_config = ConfigDict(
        json_schema_extra={"example": REGISTRATION_CREATE_EXAMPLE}
    )

    repository_location: str = Field(
        ...,
        min_length=1,
        description=(
            "Local repository path or supported remote repository URL containing "
            "a root-level croissant.jsonld file."
        ),
    )
    license_value: str | None = Field(
        default=None,
        description="Optional submitted adapter license text.",
    )
    doi: str | None = Field(
        default=None,
        description="Optional submitted DOI text.",
    )
    cff_url: str | None = Field(
        default=None,
        description="Optional submitted Citation File Format URL.",
    )

    @field_validator("repository_location")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        """Normalize required text fields and reject blank values."""
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Field must not be blank.")
        return normalized_value

    @field_validator("license_value", "doi", "cff_url")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        """Normalize optional text fields."""
        if value is None:
            return None
        normalized_value = value.strip()
        return normalized_value or None


class RegistrationCreateResponse(BaseModel):
    """Response returned after creating an adapter registration."""

    registration_id: str
    adapter_name: str
    adapter_id: str
    repository_location: str
    repository_kind: Literal["local", "remote"] | str
    created_at: datetime
    published_version: str | None = None
    license_value: str | None = None
    doi: str | None = None
    cff_url: str | None = None
    submitted_by_github_user_id: str | None = None

    @classmethod
    def from_stored(
        cls, registration: StoredRegistration
    ) -> RegistrationCreateResponse:
        """Build an API response from a stored core registration model."""
        return cls(
            registration_id=registration.registration_id,
            adapter_name=registration.adapter_name,
            adapter_id=registration.adapter_id,
            repository_location=registration.repository_location,
            repository_kind=registration.repository_kind,
            created_at=registration.created_at,
            published_version=str((registration.metadata or {}).get("version", ""))
            or None
            if registration.current_registry_entry_id
            else None,
            license_value=registration.license_value,
            doi=registration.doi,
            cff_url=registration.cff_url,
            submitted_by_github_user_id=registration.submitted_by_github_user_id,
        )


class RegistrationDetailResponse(RegistrationCreateResponse):
    """Detailed response for one stored registration."""

    latest_attempt: RegistrationAttemptResponse | None = None
    metadata_path: str | None = None
    metadata: dict[str, Any] | None = None
    profile_version: str | None = None
    updated_at: datetime | None = None
    uniqueness_key: str | None = None
    validation_errors: list[str] | None = None

    @classmethod
    def from_stored(
        cls,
        registration: StoredRegistration,
        *,
        latest_attempt: RegistrationAttemptResponse | None = None,
    ) -> RegistrationDetailResponse:
        """Build a detailed API response from a stored core registration model."""
        return cls(
            latest_attempt=latest_attempt,
            registration_id=registration.registration_id,
            adapter_name=registration.adapter_name,
            adapter_id=registration.adapter_id,
            repository_location=registration.repository_location,
            repository_kind=registration.repository_kind,
            created_at=registration.created_at,
            published_version=str((registration.metadata or {}).get("version", ""))
            or None
            if registration.current_registry_entry_id
            else None,
            license_value=registration.license_value,
            doi=registration.doi,
            cff_url=registration.cff_url,
            submitted_by_github_user_id=registration.submitted_by_github_user_id,
            metadata_path=registration.metadata_path,
            metadata=registration.metadata,
            profile_version=registration.profile_version,
            updated_at=registration.updated_at,
            uniqueness_key=registration.uniqueness_key,
            validation_errors=registration.validation_errors,
        )


class RegistrationListItemResponse(RegistrationCreateResponse):
    """Summary response model for one registration in a list."""

    latest_attempt: RegistrationAttemptResponse | None = None
    profile_version: str | None = None
    updated_at: datetime | None = None
    uniqueness_key: str | None = None

    @classmethod
    def from_stored(
        cls,
        registration: StoredRegistration,
        *,
        latest_attempt: RegistrationAttemptResponse | None = None,
    ) -> RegistrationListItemResponse:
        """Build a list item response from a stored core registration model."""
        return cls(
            latest_attempt=latest_attempt,
            registration_id=registration.registration_id,
            adapter_name=registration.adapter_name,
            adapter_id=registration.adapter_id,
            repository_location=registration.repository_location,
            repository_kind=registration.repository_kind,
            created_at=registration.created_at,
            published_version=str((registration.metadata or {}).get("version", ""))
            or None
            if registration.current_registry_entry_id
            else None,
            license_value=registration.license_value,
            doi=registration.doi,
            cff_url=registration.cff_url,
            submitted_by_github_user_id=registration.submitted_by_github_user_id,
            profile_version=registration.profile_version,
            updated_at=registration.updated_at,
            uniqueness_key=registration.uniqueness_key,
        )


class RegistrationListResponse(BaseModel):
    """Response model for a registration list."""

    items: list[RegistrationListItemResponse]


class RegistrationCroissantFilePresentCheckResponse(BaseModel):
    """Response model for a remote croissant.jsonld presence check."""

    status: Literal["FOUND", "NOT_FOUND", "UNAVAILABLE"]
    repository_url: str
    reason_code: str | None = None
    message: str
    has_croissant_file: bool


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
    def from_event(cls, event: RegistrationEvent) -> RegistrationEventResponse:
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
