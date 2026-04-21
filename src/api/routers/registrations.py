"""Registration workflow routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from src.api.dependencies import get_registration_store
from src.api.errors import (
    registration_not_found_http_error,
    registration_processing_http_error,
    registration_submission_http_error,
)
from src.api.schemas.registrations import (
    RegistrationCreateRequest,
    RegistrationCreateResponse,
    RegistrationDetailResponse,
    RegistrationEventListResponse,
    RegistrationEventResponse,
    RegistrationListItemResponse,
    RegistrationListResponse,
    RegistrationProcessResponse,
    RegistrationRevalidateResponse,
)
from src.core.registration.service import (
    finish_registration,
    revalidate_registration,
    submit_registration,
)
from src.core.registration.store import RegistrationStore


router = APIRouter()


# ===========================================================
# Registration Routes
# ===========================================================


@router.post(
    "/registrations",
    response_model=RegistrationCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit an adapter registration",
    description=(
        "Store one adapter repository as a tracked registration request. "
        "The repository may be a local path or supported remote URL and should "
        "contain a root-level croissant.jsonld file. Processing happens later "
        "through the process endpoint or a registry refresh."
    ),
)
def create_registration(
    payload: RegistrationCreateRequest,
    store: RegistrationStore = Depends(get_registration_store),
) -> RegistrationCreateResponse:
    """Create and persist a submitted adapter registration."""
    try:
        registration = submit_registration(
            adapter_name=payload.adapter_name,
            repository_location=payload.repository_location,
            store=store,
            contact_email=payload.contact_email,
        )
    except Exception as exc:  # noqa: BLE001
        raise registration_submission_http_error(exc) from exc

    return RegistrationCreateResponse.from_stored(registration)


@router.get(
    "/registrations",
    response_model=RegistrationListResponse,
    summary="List registrations",
    description=(
        "Return active registration summary rows. This list is intentionally "
        "metadata-light; use the registration detail endpoint for processing "
        "details and metadata payloads."
    ),
)
def list_registrations(
    store: RegistrationStore = Depends(get_registration_store),
) -> RegistrationListResponse:
    """Return active stored adapter registrations."""
    registrations = store.list_active_registrations()
    items = [
        RegistrationListItemResponse.from_stored(registration)
        for registration in registrations
    ]

    return RegistrationListResponse(items=items)


@router.get(
    "/registrations/{registration_id}/events",
    response_model=RegistrationEventListResponse,
    summary="List registration events",
    description=(
        "Return the event history recorded while submitting, processing, "
        "refreshing, or revalidating one registration."
    ),
)
def list_registration_events(
    registration_id: str,
    store: RegistrationStore = Depends(get_registration_store),
) -> RegistrationEventListResponse:
    """Return the event history for one stored adapter registration."""
    registration = store.get_registration(registration_id)
    if registration is None:
        raise registration_not_found_http_error(registration_id)

    events = store.list_registration_events(registration_id)
    return RegistrationEventListResponse(
        items=[RegistrationEventResponse.from_event(event) for event in events]
    )


@router.get(
    "/registrations/{registration_id}",
    response_model=RegistrationDetailResponse,
    summary="Get registration detail",
    description=(
        "Return one operator-facing registration detail record. This endpoint "
        "may include discovered metadata, metadata path, validation errors, and "
        "canonical uniqueness details."
    ),
)
def get_registration(
    registration_id: str,
    store: RegistrationStore = Depends(get_registration_store),
) -> RegistrationDetailResponse:
    """Return one stored adapter registration by identifier."""
    registration = store.get_registration(registration_id)
    if registration is None:
        raise registration_not_found_http_error(registration_id)

    return RegistrationDetailResponse.from_stored(registration)


@router.post(
    "/registrations/{registration_id}/process",
    response_model=RegistrationProcessResponse,
    summary="Process one registration",
    description=(
        "Discover the submitted repository metadata, validate the adapter and "
        "embedded datasets, update registration status, and create or reuse a "
        "canonical registry entry when valid."
    ),
)
def process_registration(
    registration_id: str,
    store: RegistrationStore = Depends(get_registration_store),
) -> RegistrationProcessResponse:
    """Discover, validate, and persist one stored registration result."""
    try:
        registration = finish_registration(
            registration_id=registration_id,
            store=store,
        )
    except Exception as exc:  # noqa: BLE001
        raise registration_processing_http_error(registration_id, exc) from exc

    return RegistrationProcessResponse.from_stored(registration)


@router.post(
    "/registrations/{registration_id}/revalidate",
    response_model=RegistrationRevalidateResponse,
    summary="Revalidate one registration",
    description=(
        "Reprocess one registration whose current status is INVALID or whose "
        "latest event is FETCH_FAILED."
    ),
)
def revalidate_registration_route(
    registration_id: str,
    store: RegistrationStore = Depends(get_registration_store),
) -> RegistrationRevalidateResponse:
    """Reprocess one previously invalid or fetch-failed registration."""
    try:
        registration = revalidate_registration(
            registration_id=registration_id,
            store=store,
        )
    except Exception as exc:  # noqa: BLE001
        raise registration_processing_http_error(registration_id, exc) from exc

    return RegistrationRevalidateResponse.from_stored(registration)
