"""Pydantic schemas for public adapter catalog API contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from src.core.registration.models import RegistryEntry


# ===========================================================
# =====================  Output Models ======================
# ===========================================================


class AdapterVersionResponse(BaseModel):
    """Response model for one registered adapter version."""

    adapter_id: str
    adapter_name: str
    adapter_version: str
    registry_entry_id: str
    profile_version: str | None = None
    metadata_checksum: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entry(cls, entry: RegistryEntry) -> "AdapterVersionResponse":
        """Build an adapter version response from a canonical registry entry."""
        return cls(
            adapter_id=adapter_id_from_uniqueness_key(entry.uniqueness_key),
            adapter_name=entry.adapter_name,
            adapter_version=entry.adapter_version,
            registry_entry_id=entry.entry_id,
            profile_version=entry.profile_version,
            metadata_checksum=entry.metadata_checksum,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
        )


class AdapterCatalogItemResponse(BaseModel):
    """Response model for one adapter catalog item."""

    adapter_id: str
    adapter_name: str
    latest_version: str
    version_count: int

    @classmethod
    def from_entries(
        cls,
        adapter_id: str,
        entries: list[RegistryEntry],
    ) -> "AdapterCatalogItemResponse":
        """Build one catalog item from the canonical entries for an adapter."""
        latest = latest_registry_entry(entries)
        return cls(
            adapter_id=adapter_id,
            adapter_name=latest.adapter_name,
            latest_version=latest.adapter_version,
            version_count=len(entries),
        )


class AdapterCatalogListResponse(BaseModel):
    """Response model for the public adapter catalog."""

    items: list[AdapterCatalogItemResponse]


class AdapterDetailResponse(BaseModel):
    """Response model for one adapter and its registered versions."""

    adapter_id: str
    adapter_name: str
    latest_version: str
    versions: list[AdapterVersionResponse]

    @classmethod
    def from_entries(
        cls,
        adapter_id: str,
        entries: list[RegistryEntry],
    ) -> "AdapterDetailResponse":
        """Build an adapter detail response from canonical entries."""
        latest = latest_registry_entry(entries)
        return cls(
            adapter_id=adapter_id,
            adapter_name=latest.adapter_name,
            latest_version=latest.adapter_version,
            versions=[AdapterVersionResponse.from_entry(entry) for entry in entries],
        )


class AdapterMetadataResponse(BaseModel):
    """Response model for one adapter version's full Croissant metadata."""

    adapter_id: str
    adapter_version: str
    registry_entry_id: str
    metadata: dict[str, Any]

    @classmethod
    def from_entry(cls, entry: RegistryEntry) -> "AdapterMetadataResponse":
        """Build a metadata response from a canonical registry entry."""
        return cls(
            adapter_id=adapter_id_from_uniqueness_key(entry.uniqueness_key),
            adapter_version=entry.adapter_version,
            registry_entry_id=entry.entry_id,
            metadata=entry.metadata or {},
        )


# ===========================================================
# =====================  Mapping Helpers ====================
# ===========================================================


def adapter_id_from_uniqueness_key(uniqueness_key: str) -> str:
    """Extract the adapter id from the canonical adapter_id::version key."""
    return uniqueness_key.rsplit("::", maxsplit=1)[0]


def latest_registry_entry(entries: list[RegistryEntry]) -> RegistryEntry:
    """Return the most recently updated entry from a non-empty entry list."""
    return max(entries, key=lambda entry: (entry.updated_at, entry.created_at))
