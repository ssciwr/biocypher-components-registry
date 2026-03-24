"""Public adapter catalog routes."""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends

from src.api.dependencies import get_registration_store
from src.api.errors import (
    adapter_not_found_http_error,
    adapter_version_not_found_http_error,
)
from src.api.schemas.adapters import (
    AdapterCatalogItemResponse,
    AdapterCatalogListResponse,
    AdapterDetailResponse,
    AdapterMetadataResponse,
    adapter_id_from_uniqueness_key,
)
from src.core.registration.models import RegistryEntry
from src.core.registration.store import RegistrationStore


router = APIRouter()


# ===========================================================
# Adapter Catalog Routes
# ===========================================================


@router.get(
    "/adapters",
    response_model=AdapterCatalogListResponse,
    summary="List public adapters",
    description=(
        "Return the public adapter catalog derived from canonical valid registry "
        "entries. Registrations that are SUBMITTED, INVALID, or FETCH_FAILED do "
        "not appear here."
    ),
)
def list_adapters(
    store: RegistrationStore = Depends(get_registration_store),
) -> AdapterCatalogListResponse:
    """Return public adapters that have at least one canonical registry entry."""
    grouped_entries = _group_entries_by_adapter_id(store.list_registry_entries())
    items = [
        AdapterCatalogItemResponse.from_entries(adapter_id, entries)
        for adapter_id, entries in sorted(grouped_entries.items())
    ]
    return AdapterCatalogListResponse(items=items)


@router.get(
    "/adapters/{adapter_id}",
    response_model=AdapterDetailResponse,
    summary="Get adapter catalog detail",
    description=(
        "Return one public adapter with its registered canonical versions. The "
        "response is metadata-light; fetch full Croissant metadata through the "
        "version metadata endpoint."
    ),
)
def get_adapter(
    adapter_id: str,
    store: RegistrationStore = Depends(get_registration_store),
) -> AdapterDetailResponse:
    """Return one public adapter with all registered canonical versions."""
    entries = _entries_for_adapter(adapter_id, store.list_registry_entries())
    if not entries:
        raise adapter_not_found_http_error(adapter_id)

    return AdapterDetailResponse.from_entries(adapter_id, entries)


@router.get(
    "/adapters/{adapter_id}/versions/{version}/metadata",
    response_model=AdapterMetadataResponse,
    summary="Get adapter version metadata",
    description=(
        "Return the full stored Croissant metadata document for one canonical "
        "adapter version."
    ),
)
def get_adapter_version_metadata(
    adapter_id: str,
    version: str,
    store: RegistrationStore = Depends(get_registration_store),
) -> AdapterMetadataResponse:
    """Return full Croissant metadata for one public adapter version."""
    entries = _entries_for_adapter(adapter_id, store.list_registry_entries())
    if not entries:
        raise adapter_not_found_http_error(adapter_id)

    entry = _entry_for_adapter_version(version, entries)
    if entry is None:
        raise adapter_version_not_found_http_error(adapter_id, version)

    return AdapterMetadataResponse.from_entry(entry)


# ===========================================================
# Route Helpers
# ===========================================================


def _group_entries_by_adapter_id(
    entries: list[RegistryEntry],
) -> dict[str, list[RegistryEntry]]:
    """Group canonical registry entries by adapter identifier."""
    grouped_entries: dict[str, list[RegistryEntry]] = defaultdict(list)
    for entry in entries:
        grouped_entries[adapter_id_from_uniqueness_key(entry.uniqueness_key)].append(
            entry
        )

    return {
        adapter_id: _sort_entries_by_version(entries)
        for adapter_id, entries in grouped_entries.items()
    }


def _entries_for_adapter(
    adapter_id: str,
    entries: list[RegistryEntry],
) -> list[RegistryEntry]:
    """Return canonical entries for one adapter in stable version order."""
    return _sort_entries_by_version(
        [
            entry
            for entry in entries
            if adapter_id_from_uniqueness_key(entry.uniqueness_key) == adapter_id
        ]
    )


def _sort_entries_by_version(entries: list[RegistryEntry]) -> list[RegistryEntry]:
    """Sort entries by creation order and version text for stable responses."""
    return sorted(
        entries,
        key=lambda entry: (entry.created_at, entry.adapter_version, entry.entry_id),
    )


def _entry_for_adapter_version(
    version: str,
    entries: list[RegistryEntry],
) -> RegistryEntry | None:
    """Return one canonical entry matching the requested adapter version."""
    for entry in entries:
        if entry.adapter_version == version:
            return entry
    return None
