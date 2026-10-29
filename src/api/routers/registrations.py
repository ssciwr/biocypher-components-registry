"""Registration workflow routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from src.api.dependencies import get_optional_auth_session, get_registration_store
from src.api.errors import (
    registration_not_found_http_error,
    registration_processing_http_error,
    registration_submission_http_error,
)
from src.api.schemas.registrations import (
    RegistrationAttemptResponse,
    RegistrationCreateRequest,
    RegistrationCroissantFilePresentCheckResponse,
    RegistrationDetailResponse,
    RegistrationEventListResponse,
    RegistrationEventResponse,
    RegistrationListItemResponse,
    RegistrationListResponse,
    RegistrationProcessResponse,
    RegistrationRevalidateResponse,
)
from src.core.auth.models import AuthSession
from src.core.registration.models import AttemptStatus
from src.core.registration.service import (
    finish_registration,
    register_adapter,
    revalidate_registration,
)
from src.core.registration.store import RegistrationStore
from src.core.shared.errors import InvalidRepoURLError, RepositoryUnavailableError
from src.core.shared.files import remote_metadata_exists
from src.core.shared.repositories import normalize_repository_url

router = APIRouter()

RegistrationStoreDep = Annotated[RegistrationStore, Depends(get_registration_store)]
OptionalAuthSessionDep = Annotated[
    AuthSession | None, Depends(get_optional_auth_session)
]


def _authorize_processing(
    registration_id: str, store: RegistrationStore, session: AuthSession | None
) -> None:
    registration = store.get_registration(registration_id)
    if registration is None:
        raise registration_not_found_http_error(registration_id)
    if registration.submitted_by_github_user_id is not None:
        if session is None:
            raise HTTPException(status_code=401, detail="GitHub sign-in required.")
        if session.github_user_id != registration.submitted_by_github_user_id:
            raise HTTPException(
                status_code=403,
                detail="Only the submitting account can process this source.",
            )


# ===========================================================
# Registration Routes
# ===========================================================


@router.post(
    "/registrations",
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {
            "model": RegistrationAttemptResponse,
            "description": "Processing failed; no first-registration records were saved.",
        },
        409: {"description": "The repository is already registered."},
    },
    summary="Submit an adapter registration",
    description=(
        "Fetch and validate metadata synchronously. Persist the registration "
        "only after acceptance; failed first registrations create no records."
    ),
)
def create_registration(
    payload: RegistrationCreateRequest,
    response: Response,
    store: RegistrationStoreDep,
    auth_session: OptionalAuthSessionDep,
) -> RegistrationAttemptResponse:
    """Return a terminal result, committing only accepted first registrations."""
    try:
        outcome = register_adapter(
            repository_location=payload.repository_location,
            store=store,
            license_value=payload.license_value,
            doi=payload.doi,
            cff_url=payload.cff_url,
            submitted_by_github_user_id=(
                auth_session.github_user_id if auth_session is not None else None
            ),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise registration_submission_http_error(exc) from exc

    if outcome.attempt_status == AttemptStatus.FAILED:
        response.status_code = status.HTTP_200_OK
    return RegistrationAttemptResponse.from_outcome(outcome)


@router.get(
    "/registrations",
    summary="List registrations",
    description=(
        "Return active registration summary rows. This list is intentionally "
        "metadata-light; use the registration detail endpoint for processing "
        "details and metadata payloads."
    ),
)
def list_registrations(
    store: RegistrationStoreDep,
) -> RegistrationListResponse:
    """Return active stored adapter registrations."""
    registrations = store.list_active_registrations()
    items = [
        RegistrationListItemResponse.from_stored(registration)
        for registration in registrations
    ]

    return RegistrationListResponse(items=items)


@router.get(
    "/registrations/croissant-file-present-check",
    summary="Check registration Croissant file presence",
    description="Return whether a remote repository exposes root-level croissant.jsonld.",
)
def check_registration_croissant_file_presence(
    repository_url: Annotated[str, Query(min_length=1)],
) -> RegistrationCroissantFilePresentCheckResponse:
    """Return whether the submitted repository exposes Croissant metadata."""
    normalized = repository_url
    try:
        normalized = normalize_repository_url(repository_url)
        present = remote_metadata_exists(normalized)
    except (InvalidRepoURLError, RepositoryUnavailableError) as exc:
        return RegistrationCroissantFilePresentCheckResponse(
            status="UNAVAILABLE",
            repository_url=normalized,
            has_croissant_file=False,
            reason_code=getattr(exc, "reason_code", "INVALID_REPOSITORY_URL"),
            message=str(exc),
        )
    return RegistrationCroissantFilePresentCheckResponse(
        status="FOUND" if present else "NOT_FOUND",
        repository_url=normalized,
        has_croissant_file=present,
        message="Croissant file found at repository root."
        if present
        else "Croissant file not found at repository root.",
    )


# previously this happened on the frontend but with Gitlab + Github support it became quite messy.
# Adding Gitlab support has added about 30 lines to the project, but we keep it simpler conceptually by only hcecking on the backend.


@router.get(
    "/registrations/{registration_id}/events",
    summary="List registration events",
    description=(
        "Return the event history recorded while submitting, processing, "
        "refreshing, or revalidating one registration."
    ),
)
def list_registration_events(
    registration_id: str,
    store: RegistrationStoreDep,
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
    summary="Get registration detail",
    description=(
        "Return one operator-facing registration detail record. This endpoint "
        "may include discovered metadata, metadata path, validation errors, and "
        "canonical uniqueness details."
    ),
)
def get_registration(
    registration_id: str,
    store: RegistrationStoreDep,
) -> RegistrationDetailResponse:
    """Return one stored adapter registration by identifier."""
    registration = store.get_registration(registration_id)
    if registration is None:
        raise registration_not_found_http_error(registration_id)

    return RegistrationDetailResponse.from_stored(registration)


@router.post(
    "/registrations/{registration_id}/process",
    summary="Process one registration",
    description=(
        "Discover the submitted repository metadata, validate the adapter and "
        "embedded datasets, update registration status, and create or reuse a "
        "canonical registry entry when valid."
    ),
)
def process_registration(
    registration_id: str,
    store: RegistrationStoreDep,
    auth_session: OptionalAuthSessionDep,
) -> RegistrationProcessResponse:
    """Discover, validate, and persist one stored registration result."""
    _authorize_processing(registration_id, store, auth_session)
    try:
        registration = finish_registration(
            registration_id=registration_id,
            store=store,
        )
    except Exception as exc:
        raise registration_processing_http_error(registration_id, exc) from exc

    return RegistrationProcessResponse.from_stored(registration)


@router.post(
    "/registrations/{registration_id}/revalidate",
    summary="Revalidate one registration",
    description=(
        "Reprocess one registration whose current status is INVALID or whose "
        "latest event is FETCH_FAILED."
    ),
)
def revalidate_registration_route(
    registration_id: str,
    store: RegistrationStoreDep,
    auth_session: OptionalAuthSessionDep,
) -> RegistrationRevalidateResponse:
    """Reprocess one previously invalid or fetch-failed registration."""
    _authorize_processing(registration_id, store, auth_session)
    try:
        registration = revalidate_registration(
            registration_id=registration_id,
            store=store,
        )
    except Exception as exc:
        raise registration_processing_http_error(registration_id, exc) from exc

    return RegistrationRevalidateResponse.from_stored(registration)
