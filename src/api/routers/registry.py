"""Registry-level workflow routes."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import get_registration_store
from src.api.errors import (
    registry_entry_not_found_http_error,
    registry_refresh_not_found_http_error,
)
from src.api.schemas.registry import (
    RegistryEntryListResponse,
    RegistryEntryResponse,
    RegistryRegistrationListResponse,
    RegistryRegistrationResponse,
    RegistryRefreshLatestResponse,
    RegistryRefreshResponse,
)
from src.core.registration.models import RegistrationStatus
from src.core.registration.service import refresh_active_registrations
from src.core.registration.store import RegistrationStore


router = APIRouter()
RegistryLatestEvent = Literal[
    "SUBMITTED",
    "VALID_CREATED",
    "UNCHANGED",
    "DUPLICATE",
    "REJECTED_SAME_VERSION_CHANGED",
    "INVALID_SCHEMA",
    "INVALID_MLCROISSANT",
    "INVALID_BOTH",
    "FETCH_FAILED",
    "REVALIDATED",
]


# ===========================================================
# Registry Routes
# ===========================================================


@router.get(
    "/registry/registrations",
    response_model=RegistryRegistrationListResponse,
    summary="List registry registrations",
    description=(
        "Return maintainer/operator rows for active registrations, including "
        "public status and latest event type. The optional filters are strict; "
        "unsupported values return 422."
    ),
)
def list_registry_registrations(
    status: RegistrationStatus | None = Query(
        default=None,
        description="Filter registry registrations by public registration status.",
    ),
    latest_event: RegistryLatestEvent | None = Query(
        default=None,
        description=(
            "Filter by latest registration event type, such as VALID_CREATED, "
            "INVALID_SCHEMA, or FETCH_FAILED."
        ),
    ),
    store: RegistrationStore = Depends(get_registration_store),
) -> RegistryRegistrationListResponse:
    """Return registry registration overview rows with latest event information."""
    items: list[RegistryRegistrationResponse] = []

    for registration in store.list_active_registrations():
        latest_event_type = (
            store.get_latest_event_type(registration.registration_id) or "SUBMITTED"
        )
        if status is not None and registration.status != status:
            continue
        if latest_event is not None and latest_event_type != latest_event:
            continue

        items.append(
            RegistryRegistrationResponse.from_registration(
                registration,
                latest_event_type=latest_event_type,
            )
        )

    return RegistryRegistrationListResponse(items=items)


@router.get(
    "/registry/entries",
    response_model=RegistryEntryListResponse,
    summary="List registry entries",
    description=(
        "Return canonical valid registry entries. This endpoint does not return "
        "full Croissant metadata; use the adapter metadata endpoint for that."
    ),
)
def list_registry_entries(
    store: RegistrationStore = Depends(get_registration_store),
) -> RegistryEntryListResponse:
    """Return canonical valid registry entries."""
    entries = store.list_registry_entries()
    return RegistryEntryListResponse(
        items=[RegistryEntryResponse.from_entry(entry) for entry in entries]
    )


@router.get(
    "/registry/entries/{entry_id}",
    response_model=RegistryEntryResponse,
    summary="Get registry entry",
    description=(
        "Return one canonical valid registry entry by registry entry id. The "
        "response is metadata-light and suitable for registry tables."
    ),
)
def get_registry_entry(
    entry_id: str,
    store: RegistrationStore = Depends(get_registration_store),
) -> RegistryEntryResponse:
    """Return one canonical valid registry entry by identifier."""
    entry = store.get_registry_entry(entry_id)
    if entry is None:
        raise registry_entry_not_found_http_error(entry_id)

    return RegistryEntryResponse.from_entry(entry)


@router.get(
    "/registry/refreshes/latest",
    response_model=RegistryRefreshLatestResponse,
    summary="Get latest registry refresh",
    description=(
        "Return the latest persisted batch refresh summary. Returns 404 if no "
        "refresh has been recorded yet."
    ),
)
def get_latest_registry_refresh(
    store: RegistrationStore = Depends(get_registration_store),
) -> RegistryRefreshLatestResponse:
    """Return the latest persisted registry refresh summary."""
    refresh = store.get_latest_batch_refresh()
    if refresh is None:
        raise registry_refresh_not_found_http_error()

    return RegistryRefreshLatestResponse.from_record(refresh)


@router.post(
    "/registry/refreshes",
    response_model=RegistryRefreshResponse,
    summary="Run registry refresh",
    description=(
        "Process every active registration once, continue past per-source "
        "failures, persist the refresh summary, and return aggregate outcome "
        "counts."
    ),
)
def create_registry_refresh(
    store: RegistrationStore = Depends(get_registration_store),
) -> RegistryRefreshResponse:
    """Process all active registration sources once."""
    return _refresh_registry_response(store)


# ===========================================================
# Route Helpers
# ===========================================================


def _refresh_registry_response(store: RegistrationStore) -> RegistryRefreshResponse:
    """Process all active registration sources once and serialize the summary."""
    summary = refresh_active_registrations(store=store)
    return RegistryRefreshResponse.from_summary(summary)
