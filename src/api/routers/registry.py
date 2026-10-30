"""Registry-level workflow routes."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import get_registration_store
from src.api.errors import (
    registry_entry_not_found_http_error,
    registry_refresh_not_found_http_error,
)
from src.api.schemas.registrations import RegistrationAttemptResponse
from src.api.schemas.registry import (
    RegistryEntryListResponse,
    RegistryEntryResponse,
    RegistryRefreshLatestResponse,
    RegistryRegistrationListResponse,
    RegistryRegistrationResponse,
)
from src.core.registration.service import (
    latest_processing_outcome,
)
from src.core.registration.store import RegistrationStore

router = APIRouter()
RegistrationStoreDep = Annotated[RegistrationStore, Depends(get_registration_store)]
RegistryLatestEvent = Literal[
    "VALID_CREATED",
    "UNCHANGED",
    "DUPLICATE",
    "REJECTED_SAME_VERSION_CHANGED",
    "INVALID_SCHEMA",
    "INVALID_MLCROISSANT",
    "INVALID_BOTH",
    "FETCH_FAILED",
    "SCHEMA_INVALID",
    "SEMANTICS_INVALID",
    "MLCROISSANT_INVALID",
    "INVALID_JSON",
    "METADATA_NOT_FOUND",
    "REPOSITORY_UNAVAILABLE",
    "REMOTE_TEMPORARY",
    "DEFAULT_BRANCH_UNRESOLVED",
    "METADATA_TOO_LARGE",
    "VERSION_NOT_BUMPED",
    "ADAPTER_ID_CHANGED",
]


# ===========================================================
# Registry Routes
# ===========================================================


@router.get(
    "/registry/registrations",
    summary="List registry registrations",
    description=(
        "Return maintainer/operator rows for active registrations, including "
        "latest event type. The optional filters are strict; "
        "unsupported values return 422."
    ),
)
def list_registry_registrations(
    store: RegistrationStoreDep,
    latest_event: Annotated[
        RegistryLatestEvent | None,
        Query(
            description=(
                "Filter by latest registration event type, such as VALID_CREATED, "
                "INVALID_SCHEMA, or FETCH_FAILED."
            )
        ),
    ] = None,
) -> RegistryRegistrationListResponse:
    """Return registry registration overview rows with latest event information."""
    items: list[RegistryRegistrationResponse] = []

    for registration in store.list_active_registrations():
        latest_event_type = (
            store.get_latest_event_type(registration.registration_id) or ""
        )
        if latest_event is not None and latest_event_type != latest_event:
            continue

        items.append(
            RegistryRegistrationResponse.from_registration(
                registration,
                latest_event_type=latest_event_type,
                latest_attempt=RegistrationAttemptResponse.from_outcome(outcome)
                if (outcome := latest_processing_outcome(registration, store))
                else None,
            )
        )

    return RegistryRegistrationListResponse(items=items)


@router.get(
    "/registry/entries",
    summary="List registry entries",
    description=(
        "Return canonical valid registry entries. This endpoint does not return "
        "full Croissant metadata; use the adapter metadata endpoint for that."
    ),
)
def list_registry_entries(
    store: RegistrationStoreDep,
) -> RegistryEntryListResponse:
    """Return canonical valid registry entries."""
    entries = store.list_registry_entries()
    return RegistryEntryListResponse(
        items=[RegistryEntryResponse.from_entry(entry) for entry in entries]
    )


@router.get(
    "/registry/entries/{entry_id}",
    summary="Get registry entry",
    description=(
        "Return one canonical valid registry entry by registry entry id. The "
        "response is metadata-light and suitable for registry tables."
    ),
)
def get_registry_entry(
    entry_id: str,
    store: RegistrationStoreDep,
) -> RegistryEntryResponse:
    """Return one canonical valid registry entry by identifier."""
    entry = store.get_registry_entry(entry_id)
    if entry is None:
        raise registry_entry_not_found_http_error(entry_id)

    return RegistryEntryResponse.from_entry(entry)


@router.get(
    "/registry/refreshes/latest",
    summary="Get latest registry refresh",
    description=(
        "Return the latest persisted batch refresh summary. Returns 404 if no "
        "refresh has been recorded yet."
    ),
)
def get_latest_registry_refresh(
    store: RegistrationStoreDep,
) -> RegistryRefreshLatestResponse:
    """Return the latest persisted registry refresh summary."""
    refresh = store.get_latest_batch_refresh()
    if refresh is None:
        raise registry_refresh_not_found_http_error()

    return RegistryRefreshLatestResponse.from_record(refresh)
