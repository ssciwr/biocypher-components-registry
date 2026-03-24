"""Shared registration store interface used by persistence backends."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from typing import Any

from src.core.adapter.request import AdapterRegistrationRequest
from src.core.registration.models import (
    BatchRefreshRecord,
    BatchRefreshSummary,
    RegistrationEvent,
    RegistryEntry,
    StoredRegistration,
)


class RegistrationStore(Protocol):
    """Defines the methods required to persist registration requests."""

    def create_registration(
        self,
        request: AdapterRegistrationRequest,
    ) -> StoredRegistration:
        """Store a new registration request and return the saved record."""

    def get_registration(self, registration_id: str) -> StoredRegistration | None:
        """Return one stored registration by identifier when it exists."""

    def list_active_registration_ids(self) -> list[str]:
        """Return all active registration identifiers to process in a batch run."""

    def list_active_registrations(self) -> list[StoredRegistration]:
        """Return all active registrations in stable creation order."""

    def get_latest_event_type(self, registration_id: str) -> str | None:
        """Return the latest recorded event type for one registration when it exists."""

    def list_registration_events(self, registration_id: str) -> list[RegistrationEvent]:
        """Return event history for one registration in chronological order."""

    def list_registry_entries(self) -> list[RegistryEntry]:
        """Return active canonical registry entries in stable creation order."""

    def get_registry_entry(self, entry_id: str) -> RegistryEntry | None:
        """Return one active canonical registry entry by identifier when it exists."""

    def record_batch_refresh(
        self,
        summary: BatchRefreshSummary,
        started_at: datetime,
        finished_at: datetime,
    ) -> BatchRefreshRecord:
        """Persist one batch refresh summary."""

    def get_latest_batch_refresh(self) -> BatchRefreshRecord | None:
        """Return the most recent batch refresh summary when one exists."""

    def mark_registration_valid(
        self,
        registration_id: str,
        metadata: dict[str, Any],
        metadata_path: str | None,
        profile_version: str,
        uniqueness_key: str,
        observed_checksum: str,
    ) -> StoredRegistration:
        """Persist approved metadata and update the registration status."""

    def mark_registration_invalid(
        self,
        registration_id: str,
        errors: list[str],
        profile_version: str | None,
        metadata: dict[str, Any] | None = None,
        metadata_path: str | None = None,
        event_type: str = "INVALID_SCHEMA",
        mlcroissant_valid: bool | None = None,
        schema_valid: bool | None = None,
        observed_checksum: str | None = None,
    ) -> StoredRegistration:
        """Persist failed validation details and update the registration status."""

    def mark_registration_fetch_failed(
        self,
        registration_id: str,
        error_message: str,
    ) -> StoredRegistration:
        """Persist one fetch/discovery failure without stopping batch processing."""

    def record_revalidation_requested(self, registration_id: str) -> None:
        """Persist that one source was explicitly revalidated on demand."""
