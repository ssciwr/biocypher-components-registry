"""Data models used by the adapter registration flow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class RegistrationStatus(StrEnum):
    """Tracked states for a stored registration request."""

    SUBMITTED = "SUBMITTED"
    VALID = "VALID"
    INVALID = "INVALID"


@dataclass(slots=True, frozen=True)
class StoredRegistration:
    """Represents a registration request saved in the database.

    Args:
        registration_id: Unique identifier for the stored submission.
        adapter_name: Human-readable adapter name.
        adapter_id: Stable slug identifier for the adapter.
        repository_location: Normalized repository path or URL.
        repository_kind: Repository location type.
        status: Current tracked status for the submission.
        created_at: Timestamp when the submission was stored.
        contact_email: Optional maintainer contact email for status follow-up.
        metadata_path: Stored croissant metadata file path when available.
        metadata: Persisted adapter metadata for approved registrations.
        profile_version: Validation profile version used for approval.
        updated_at: Timestamp when the record was last updated.
        last_checked_at: Timestamp when discovery or validation last ran.
        current_registry_entry_id: Identifier of the active canonical entry, if any.
        uniqueness_key: Canonical uniqueness value used for duplicate detection.
    """

    registration_id: str
    adapter_name: str
    adapter_id: str
    repository_location: str
    repository_kind: str
    status: RegistrationStatus
    created_at: datetime
    contact_email: str | None = None
    metadata_path: str | None = None
    metadata: dict[str, Any] | None = None
    profile_version: str | None = None
    updated_at: datetime | None = None
    last_checked_at: datetime | None = None
    current_registry_entry_id: str | None = None
    uniqueness_key: str | None = None
    validation_errors: list[str] | None = None


@dataclass(slots=True, frozen=True)
class RegistrationEvent:
    """Represents one event recorded for a registration source."""

    event_id: str
    source_id: str
    event_type: str
    started_at: datetime
    finished_at: datetime
    registry_entry_id: str | None = None
    message: str | None = None
    profile_version: str | None = None
    error_details: list[str] | None = None
    observed_checksum: str | None = None
    mlcroissant_valid: bool | None = None
    schema_valid: bool | None = None


@dataclass(slots=True, frozen=True)
class RegistryEntry:
    """Represents one canonical valid registry entry."""

    entry_id: str
    source_id: str
    adapter_name: str
    adapter_version: str
    uniqueness_key: str
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] | None = None
    profile_version: str | None = None
    metadata_checksum: str | None = None
    is_active: bool = True


@dataclass(slots=True, frozen=True)
class BatchRefreshSummary:
    """Summarize one batch refresh run across all active registration sources."""

    active_sources: int = 0
    processed: int = 0
    valid_created: int = 0
    unchanged: int = 0
    invalid: int = 0
    duplicate: int = 0
    rejected_same_version_changed: int = 0
    fetch_failed: int = 0


@dataclass(slots=True, frozen=True)
class BatchRefreshRecord:
    """Represents one persisted batch refresh run."""

    refresh_id: str
    started_at: datetime
    finished_at: datetime
    active_sources: int = 0
    processed: int = 0
    valid_created: int = 0
    unchanged: int = 0
    invalid: int = 0
    duplicate: int = 0
    rejected_same_version_changed: int = 0
    fetch_failed: int = 0
