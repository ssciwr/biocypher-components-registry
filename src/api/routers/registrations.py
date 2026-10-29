"""Registration workflow routes."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse

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
    RegistrationStreamEvent,
    ValidationCheckResponse,
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
from src.core.validation.progress import CheckObserver, ValidationProgress
from src.core.validation.results import ValidationCheckReport

router = APIRouter()
HEARTBEAT_SECONDS = 15
# Retain workers on disconnect: processing may already have committed. Never resubmit.
_processing_tasks: set[asyncio.Task] = set()

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
    result = _submit_registration(payload, store, auth_session)
    if result.attempt_status == AttemptStatus.FAILED:
        response.status_code = status.HTTP_200_OK
    return result


def _submit_registration(
    payload: RegistrationCreateRequest,
    store: RegistrationStore,
    auth_session: AuthSession | None,
    on_check: CheckObserver | None = None,
) -> RegistrationAttemptResponse:
    try:
        outcome = register_adapter(
            repository_location=payload.repository_location,
            store=store,
            on_check=on_check,
            license_value=payload.license_value,
            doi=payload.doi,
            cff_url=payload.cff_url,
            submitted_by_github_user_id=(
                auth_session.github_user_id if auth_session is not None else None
            ),
        )
        return RegistrationAttemptResponse.from_outcome(outcome)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise registration_submission_http_error(exc) from exc


class RegistrationEventStreamResponse(StreamingResponse):
    media_type = "text/event-stream"


async def _registration_events(
    payload: RegistrationCreateRequest,
    store: RegistrationStore,
    auth_session: AuthSession | None,
) -> AsyncIterator[str]:
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[RegistrationStreamEvent] = asyncio.Queue()
    connected = True

    def enqueue(event: RegistrationStreamEvent) -> None:
        if connected:
            queue.put_nowait(event)

    def publish(event: RegistrationStreamEvent) -> None:
        if connected:
            loop.call_soon_threadsafe(enqueue, event)

    def on_check(check: ValidationCheckReport) -> None:
        publish(
            RegistrationStreamEvent(
                type="check", check=ValidationCheckResponse.model_validate(check)
            )
        )

    def process() -> None:
        try:
            result = _submit_registration(payload, store, auth_session, on_check)
            publish(RegistrationStreamEvent(type="result", result=result))
        except HTTPException as exc:
            publish(
                RegistrationStreamEvent(
                    type="error", status_code=exc.status_code, detail=str(exc.detail)
                )
            )

    def encode(event: RegistrationStreamEvent) -> str:
        return f"event: {event.type}\ndata: {event.model_dump_json()}\n\n"

    try:
        yield encode(
            RegistrationStreamEvent(
                type="snapshot",
                checks=[
                    ValidationCheckResponse.model_validate(check)
                    for check in ValidationProgress(
                        include_file=True, include_datasets=True
                    ).reports
                ],
            )
        )
        worker = asyncio.create_task(asyncio.to_thread(process))
        _processing_tasks.add(worker)
        worker.add_done_callback(_processing_tasks.discard)
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
            except TimeoutError:
                yield ": heartbeat\n\n"
                continue
            yield encode(event)
            if event.type in {"result", "error"}:
                break
    finally:
        connected = False
        while not queue.empty():
            queue.get_nowait()


@router.post(
    "/registrations/stream",
    response_class=RegistrationEventStreamResponse,
    response_model=RegistrationStreamEvent,
    responses={200: {"model": RegistrationStreamEvent}},
    summary="Register an adapter with live validation progress",
    description="One submission per connection. Terminal result follows persistence. Do not automatically reconnect or retry this POST.",
)
async def stream_registration(
    payload: RegistrationCreateRequest,
    store: RegistrationStoreDep,
    auth_session: OptionalAuthSessionDep,
) -> StreamingResponse:
    return RegistrationEventStreamResponse(
        _registration_events(payload, store, auth_session),
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


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
