"""Pydantic schemas for registry-level API contracts."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from src.core.registration.models import (
    BatchRefreshRecord,
    BatchRefreshSummary,
    RegistrationStatus,
    RegistryEntry,
    StoredRegistration,
)


# ===========================================================
# =====================  Output Models ======================
# ===========================================================


class RegistryRefreshResponse(BaseModel):
    """Response returned after refreshing active registration sources."""

    active_sources: int
    processed: int
    valid_created: int
    unchanged: int
    invalid: int
    duplicate: int
    rejected_same_version_changed: int
    fetch_failed: int

    @classmethod
    def from_summary(cls, summary: BatchRefreshSummary) -> "RegistryRefreshResponse":
        """Build an API response from a core batch refresh summary."""
        return cls(
            active_sources=summary.active_sources,
            processed=summary.processed,
            valid_created=summary.valid_created,
            unchanged=summary.unchanged,
            invalid=summary.invalid,
            duplicate=summary.duplicate,
            rejected_same_version_changed=summary.rejected_same_version_changed,
            fetch_failed=summary.fetch_failed,
        )


class RegistryRefreshLatestResponse(BaseModel):
    """Response model for the latest persisted registry refresh."""

    refresh_id: str
    started_at: datetime
    finished_at: datetime
    active_sources: int
    processed: int
    valid_created: int
    unchanged: int
    invalid: int
    duplicate: int
    rejected_same_version_changed: int
    fetch_failed: int

    @classmethod
    def from_record(
        cls,
        record: BatchRefreshRecord,
    ) -> "RegistryRefreshLatestResponse":
        """Build an API response from a persisted core refresh record."""
        return cls(
            refresh_id=record.refresh_id,
            started_at=record.started_at,
            finished_at=record.finished_at,
            active_sources=record.active_sources,
            processed=record.processed,
            valid_created=record.valid_created,
            unchanged=record.unchanged,
            invalid=record.invalid,
            duplicate=record.duplicate,
            rejected_same_version_changed=record.rejected_same_version_changed,
            fetch_failed=record.fetch_failed,
        )


class RegistryRegistrationResponse(BaseModel):
    """Response model for one registry registration overview row."""

    registration_id: str
    adapter_name: str
    adapter_id: str
    repository_kind: str
    repository_location: str
    status: RegistrationStatus
    latest_event_type: str
    created_at: datetime
    updated_at: datetime | None = None
    contact_email: str | None = None
    profile_version: str | None = None
    uniqueness_key: str | None = None

    @classmethod
    def from_registration(
        cls,
        registration: StoredRegistration,
        *,
        latest_event_type: str,
    ) -> "RegistryRegistrationResponse":
        """Build a registry registration row from a stored registration."""
        return cls(
            registration_id=registration.registration_id,
            adapter_name=registration.adapter_name,
            adapter_id=registration.adapter_id,
            repository_kind=registration.repository_kind,
            repository_location=registration.repository_location,
            status=registration.status,
            latest_event_type=latest_event_type,
            created_at=registration.created_at,
            updated_at=registration.updated_at,
            contact_email=registration.contact_email,
            profile_version=registration.profile_version,
            uniqueness_key=registration.uniqueness_key,
        )


class RegistryRegistrationListResponse(BaseModel):
    """Response model for registry registration overview rows."""

    items: list[RegistryRegistrationResponse]


class RegistryEntryResponse(BaseModel):
    """Response model for one canonical registry entry."""

    entry_id: str
    source_id: str
    adapter_name: str
    adapter_version: str
    profile_version: str | None = None
    uniqueness_key: str
    metadata_checksum: str | None = None
    created_at: datetime
    updated_at: datetime
    is_active: bool

    @classmethod
    def from_entry(cls, entry: RegistryEntry) -> "RegistryEntryResponse":
        """Build an API response from a core registry entry model."""
        return cls(
            entry_id=entry.entry_id,
            source_id=entry.source_id,
            adapter_name=entry.adapter_name,
            adapter_version=entry.adapter_version,
            profile_version=entry.profile_version,
            uniqueness_key=entry.uniqueness_key,
            metadata_checksum=entry.metadata_checksum,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
            is_active=entry.is_active,
        )


class RegistryEntryListResponse(BaseModel):
    """Response model for canonical registry entries."""

    items: list[RegistryEntryResponse]
