"""Pydantic schemas for public adapter catalog API contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from src.core.registration.models import RegistryEntry, StoredRegistration


# ===========================================================
# =====================  Output Models ======================
# ===========================================================


class AdapterEndorsementResponse(BaseModel):
    """Current endorsement state for one adapter."""

    adapter_id: str
    endorsement_count: int
    endorsed_by_current_user: bool = False


class AdapterMaintainerResponse(BaseModel):
    """GitHub maintainer identity for adapter catalog display."""

    github_login: str
    avatar_url: str

    @classmethod
    def from_login(cls, github_login: str) -> "AdapterMaintainerResponse":
        """Build a public GitHub avatar reference from a login."""
        return cls(
            github_login=github_login,
            avatar_url=f"https://github.com/{github_login}.png",
        )


class AdapterDataSourceResponse(BaseModel):
    """Metadata-light dataset summary embedded in adapter Croissant metadata."""

    name: str
    description: str | None = None
    version: str | None = None
    license: str | None = None
    url: str | None = None
    column_count: int | None = None


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
    endorsement_count: int = 0

    @classmethod
    def from_entries(
        cls,
        adapter_id: str,
        entries: list[RegistryEntry],
        endorsement_count: int = 0,
    ) -> "AdapterCatalogItemResponse":
        """Build one catalog item from the canonical entries for an adapter."""
        latest = latest_registry_entry(entries)
        return cls(
            adapter_id=adapter_id,
            adapter_name=latest.adapter_name,
            latest_version=latest.adapter_version,
            version_count=len(entries),
            endorsement_count=endorsement_count,
        )


class AdapterLatestItemResponse(BaseModel):
    """Response model for one latest-adapters card."""

    adapter_id: str
    adapter_name: str
    latest_version: str
    description: str | None = None
    repository_location: str | None = None
    keywords: list[str] = Field(default_factory=list)
    maintainers: list[AdapterMaintainerResponse] = Field(default_factory=list)
    endorsement_count: int = 0
    endorsed_by_current_user: bool = False
    updated_at: datetime

    @classmethod
    def from_entry(
        cls,
        entry: RegistryEntry,
        registration: StoredRegistration | None,
        endorsement_count: int = 0,
        endorsed_by_current_user: bool = False,
    ) -> "AdapterLatestItemResponse":
        """Build a compact catalog card from entry and source data."""
        metadata = entry.metadata or {}
        login = registration.submitted_by_github_login if registration else None
        return cls(
            adapter_id=adapter_id_from_uniqueness_key(entry.uniqueness_key),
            adapter_name=entry.adapter_name,
            latest_version=entry.adapter_version,
            description=_metadata_text(metadata, "description"),
            repository_location=(
                registration.repository_location if registration else _metadata_text(metadata, "codeRepository")
            ),
            keywords=_metadata_list(metadata, "keywords"),
            maintainers=[AdapterMaintainerResponse.from_login(login)] if login else [],
            endorsement_count=endorsement_count,
            endorsed_by_current_user=endorsed_by_current_user,
            updated_at=entry.updated_at,
        )


class AdapterCatalogListResponse(BaseModel):
    """Response model for the public adapter catalog."""

    items: list[AdapterCatalogItemResponse]


class AdapterLatestListResponse(BaseModel):
    """Response model for newest adapter cards."""

    items: list[AdapterLatestItemResponse]


class AdapterDetailResponse(BaseModel):
    """Response model for one adapter and its registered versions."""

    adapter_id: str
    adapter_name: str
    latest_version: str
    description: str | None = None
    repository_location: str | None = None
    license_value: str | None = None
    doi: str | None = None
    cff_url: str | None = None
    keywords: list[str] = Field(default_factory=list)
    maintainers: list[AdapterMaintainerResponse] = Field(default_factory=list)
    data_sources: list[AdapterDataSourceResponse] = Field(default_factory=list)
    versions: list[AdapterVersionResponse]
    endorsement_count: int = 0
    endorsed_by_current_user: bool = False

    @classmethod
    def from_entries(
        cls,
        adapter_id: str,
        entries: list[RegistryEntry],
        registration: StoredRegistration | None = None,
        endorsement_count: int = 0,
        endorsed_by_current_user: bool = False,
    ) -> "AdapterDetailResponse":
        """Build adapter detail from canonical versions and source data."""
        latest = latest_registry_entry(entries)
        metadata = latest.metadata or {}
        login = registration.submitted_by_github_login if registration else None
        return cls(
            adapter_id=adapter_id,
            adapter_name=latest.adapter_name,
            latest_version=latest.adapter_version,
            description=_metadata_text(metadata, "description"),
            repository_location=(
                registration.repository_location if registration else _metadata_text(metadata, "codeRepository")
            ),
            license_value=(
                registration.license_value if registration and registration.license_value else _metadata_text(metadata, "license")
            ),
            doi=registration.doi if registration else None,
            cff_url=registration.cff_url if registration else None,
            keywords=_metadata_list(metadata, "keywords"),
            maintainers=[AdapterMaintainerResponse.from_login(login)] if login else [],
            data_sources=data_sources_from_metadata(metadata),
            versions=[AdapterVersionResponse.from_entry(entry) for entry in entries],
            endorsement_count=endorsement_count,
            endorsed_by_current_user=endorsed_by_current_user,
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


def data_sources_from_metadata(metadata: dict[str, Any]) -> list[AdapterDataSourceResponse]:
    """Extract embedded Croissant dataset summaries for detail pages."""
    has_part = metadata.get("hasPart")
    raw_sources = has_part if isinstance(has_part, list) else [has_part]
    data_sources: list[AdapterDataSourceResponse] = []
    for item in raw_sources:
        if not isinstance(item, dict):
            continue
        name = _metadata_text(item, "name")
        if not name:
            continue
        data_sources.append(
            AdapterDataSourceResponse(
                name=name,
                description=_metadata_text(item, "description"),
                version=_metadata_text(item, "version"),
                license=_metadata_text(item, "license"),
                url=_metadata_text(item, "url"),
                column_count=_record_set_column_count(item),
            )
        )
    return data_sources


def _metadata_text(metadata: dict[str, Any], key: str) -> str | None:
    """Normalize one optional metadata text field."""
    value = metadata.get(key)
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return None


def _metadata_list(metadata: dict[str, Any], key: str) -> list[str]:
    """Normalize list-like metadata values for public responses."""
    value = metadata.get(key)
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _record_set_column_count(dataset: dict[str, Any]) -> int | None:
    """Count Croissant record-set fields when present."""
    record_sets = dataset.get("recordSet")
    raw_record_sets = record_sets if isinstance(record_sets, list) else [record_sets]
    count = 0
    for record_set in raw_record_sets:
        if not isinstance(record_set, dict):
            continue
        fields = record_set.get("field")
        if isinstance(fields, list):
            count += len(fields)
        elif isinstance(fields, dict):
            count += 1
    return count or None
