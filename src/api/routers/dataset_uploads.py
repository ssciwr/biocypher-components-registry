"""Ephemeral, raw-body dataset upload and generation routes."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status

from src.api.dependencies import get_upload_session_manager
from src.api.schemas.dataset_uploads import (
    UploadArtifactResponse,
    UploadDeleteResponse,
    UploadFinalizeAcceptedResponse,
    UploadFinalizeResponse,
    UploadSessionCreateRequest,
    UploadSessionCreateResponse,
    UploadSessionStatusResponse,
)
from src.api.schemas.metadata import MetadataValidationResponse
from src.core.dataset.backends.auto_select import select_generator
from src.core.dataset.request import GenerationRequest
from src.core.dataset.service import execute_request as execute_dataset_request
from src.core.dataset.upload.errors import UploadSessionError
from src.core.dataset.upload.limits import (
    MAX_ARTIFACT_BYTES,
    MAX_GENERATED_JSON_BYTES,
    SESSION_START_TTL_SECONDS,
)
from src.core.dataset.upload.models import (
    UploadGenerationOptions,
    UploadInventoryEntry,
    UploadSession,
    UploadSessionState,
)
from src.core.dataset.upload.reconciliation import reconcile_generated_metadata
from src.core.dataset.upload.service import UploadSessionManager
from src.core.validation import validate_dataset

router = APIRouter()
_NO_STORE = "no-store, max-age=0"


@router.post(
    "/metadata/upload-sessions",
    response_model=UploadSessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        429: {
            "description": "The session or scratch-byte admission limit is full.",
            "headers": {
                "Retry-After": {
                    "description": "Seconds before retrying admission.",
                    "schema": {"type": "integer"},
                }
            },
        },
    },
)
async def create_upload_session(
    payload: UploadSessionCreateRequest,
    response: Response,
    manager: Annotated[UploadSessionManager, Depends(get_upload_session_manager)],
) -> UploadSessionCreateResponse:
    """Create an in-memory session after validating its complete inventory."""
    _no_store(response)
    try:
        session, token = await manager.create(
            source_kind=payload.source_kind,
            source_name=payload.source_name,
            entries=[
                UploadInventoryEntry(
                    **entry.model_dump(exclude={"artifact_size"}),
                    declared_artifact_size=entry.artifact_size,
                )
                for entry in payload.entries
            ],
            generation=UploadGenerationOptions(
                generator=payload.generation.generator,
                validate=payload.generation.run_validation,
                name=payload.generation.name,
                description=payload.generation.description,
                url=payload.generation.url,
                license_value=payload.generation.license_value,
                citation=payload.generation.citation,
                dataset_version=payload.generation.dataset_version,
                date_published=payload.generation.date_published,
                creators=payload.generation.creators,
            ),
        )
    except (UploadSessionError, ValueError) as exc:
        _raise_upload_http(exc)
    return UploadSessionCreateResponse(
        session_id=session.session_id,
        token=token,
        max_artifact_bytes=MAX_ARTIFACT_BYTES,
        expires_in_seconds=SESSION_START_TTL_SECONDS,
    )


@router.put(
    "/metadata/upload-sessions/{session_id}/artifacts/{entry_id}",
    response_model=UploadArtifactResponse,
)
async def upload_artifact(
    session_id: str,
    entry_id: str,
    request: Request,
    response: Response,
    manager: Annotated[UploadSessionManager, Depends(get_upload_session_manager)],
    authorization: Annotated[str | None, Header()] = None,
    artifact_sha256: Annotated[str | None, Header(alias="X-Artifact-SHA256")] = None,
    original_sha256: Annotated[str | None, Header(alias="X-Original-SHA256")] = None,
) -> UploadArtifactResponse:
    """Receive one raw artifact body and verify its declared identity."""
    _no_store(response)
    session = _authorize(manager, session_id, authorization)
    if request.headers.get("content-encoding", "identity").lower() != "identity":
        raise HTTPException(415, "Content-Encoding is not supported.")
    content_length_value = request.headers.get("content-length")
    if content_length_value is None:
        raise HTTPException(411, "Content-Length is required.")
    try:
        content_length = int(content_length_value)
    except ValueError as exc:
        raise HTTPException(400, "Content-Length must be an integer.") from exc
    if not artifact_sha256 or not original_sha256:
        raise HTTPException(
            400, "Both artifact and original SHA-256 headers are required."
        )
    try:
        entry = await manager.upload_artifact(
            session=session,
            entry_id=entry_id,
            body=request.stream(),
            content_length=content_length,
            artifact_sha256=artifact_sha256,
            original_sha256=original_sha256,
        )
    except (UploadSessionError, ValueError) as exc:
        _raise_upload_http(exc)
    return UploadArtifactResponse(
        entry_id=entry.entry_id,
        artifact_size=entry.artifact_size,
        artifact_sha256=entry.artifact_sha256 or "",
        complete_entries=session.complete_entries,
        total_entries=len(session.entries),
    )


@router.post(
    "/metadata/upload-sessions/{session_id}/finalize",
    response_model=UploadFinalizeAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def finalize_upload_session(
    session_id: str,
    response: Response,
    manager: Annotated[UploadSessionManager, Depends(get_upload_session_manager)],
    authorization: Annotated[str | None, Header()] = None,
) -> UploadFinalizeAcceptedResponse:
    """Idempotently enqueue generation and return immediately."""
    _no_store(response)
    session = _authorize(manager, session_id, authorization)
    try:

        async def generate(current: UploadSession) -> object:
            generated, generator_name, generation_warnings = await _run_generation(
                current
            )
            validation_result = await asyncio.to_thread(validate_dataset, generated)
            validation = MetadataValidationResponse.from_result(
                kind="dataset", result=validation_result
            )
            return UploadFinalizeResponse(
                metadata=generated,
                generator=generator_name,
                validation=validation,
                warnings=generation_warnings,
            ).model_dump(mode="json")

        await manager.enqueue_generation(session, generate)
        return UploadFinalizeAcceptedResponse(status=session.state.value)
    except (UploadSessionError, OSError, RuntimeError, ValueError) as exc:
        _raise_upload_http(exc)


@router.get(
    "/metadata/upload-sessions/{session_id}",
    response_model=UploadSessionStatusResponse,
)
async def get_upload_session_status(
    session_id: str,
    response: Response,
    manager: Annotated[UploadSessionManager, Depends(get_upload_session_manager)],
    authorization: Annotated[str | None, Header()] = None,
) -> UploadSessionStatusResponse:
    _no_store(response)
    session = _authorize(manager, session_id, authorization)
    result = session.terminal_result
    if result is not None:
        return UploadSessionStatusResponse(
            status=session.state.value,
            result=result.value,
            error=result.error,
        )
    response.headers["Retry-After"] = "1"
    return UploadSessionStatusResponse(status=session.state.value)


@router.delete(
    "/metadata/upload-sessions/{session_id}", response_model=UploadDeleteResponse
)
async def delete_upload_session(
    session_id: str,
    response: Response,
    manager: Annotated[UploadSessionManager, Depends(get_upload_session_manager)],
    authorization: Annotated[str | None, Header()] = None,
) -> UploadDeleteResponse:
    """Cancel a session and idempotently delete every scratch artifact."""
    _no_store(response)
    session = _authorize(manager, session_id, authorization)
    if session.state in {UploadSessionState.FINALIZE_QUEUED, UploadSessionState.PROCESSING}:
        raise HTTPException(409, "Generation cannot be cancelled after finalization starts.")
    await manager.destroy(session_id)
    return UploadDeleteResponse()


def _generate_and_reconcile(
    session: UploadSession,
) -> tuple[dict[str, object], Literal["croissant-baker", "native"], list[str]]:
    output_path = session.root / "dataset.jsonld"
    # Baker's contract is directory-based. A single selected file is therefore
    # placed in its isolated input directory and uses the same backend path as
    # a folder selection; the browser still declares a one-entry inventory.
    input_path = session.input_root
    options = session.generation
    request = GenerationRequest(
        input_path=str(input_path),
        output_path=str(output_path),
        validate=False,
        name=options.name or session.source_name,
        description=options.description,
        url=options.url,
        license_value=options.license_value,
        citation=options.citation,
        dataset_version=options.dataset_version,
        date_published=options.date_published,
        creators=options.creators,
    )
    requested_generator = options.generator
    if requested_generator == "auto":
        selected, _ = select_generator()
        generator_name = selected.name
    else:
        generator_name = requested_generator
    if generator_name not in {"croissant-baker", "native"}:
        raise UploadSessionError("No supported generator was selected.")
    try:
        result = execute_dataset_request(request=request, generator=generator_name)
    except RuntimeError as exc:
        raise UploadSessionError(
            "Dataset generation failed. Verify the selected CSV/TSV source and metadata."
        ) from exc
    document = result.document or _load_bounded_json(output_path)
    reconciled = reconcile_generated_metadata(document, session)
    return reconciled, generator_name, result.warnings


async def _run_generation(
    session: UploadSession,
) -> tuple[dict[str, object], Literal["croissant-baker", "native"], list[str]]:
    """Keep the bounded child alive through cancellation, then permit cleanup."""
    task = asyncio.create_task(asyncio.to_thread(_generate_and_reconcile, session))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        try:
            await asyncio.shield(task)
        finally:
            raise


def _load_bounded_json(path: Path) -> dict[str, object]:
    size = path.stat().st_size
    if size > MAX_GENERATED_JSON_BYTES:
        raise UploadSessionError("Generated metadata exceeds the response size limit.")
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise UploadSessionError("The generator did not produce a JSON object.")
    return document


def _authorize(
    manager: UploadSessionManager, session_id: str, authorization: str | None
) -> UploadSession:
    token = _bearer_token(authorization)
    try:
        return manager.authorize(session_id, token)
    except UploadSessionError as exc:
        _raise_upload_http(exc)


def _bearer_token(authorization: str | None) -> str:
    prefix = "Bearer "
    return (
        authorization[len(prefix) :].strip()
        if authorization and authorization.startswith(prefix)
        else ""
    )


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = _NO_STORE
    response.headers["Pragma"] = "no-cache"


def _raise_upload_http(exc: Exception) -> None:
    status_code = exc.status_code if isinstance(exc, UploadSessionError) else 400
    headers = None
    if isinstance(exc, UploadSessionError) and exc.retry_after is not None:
        headers = {"Retry-After": str(exc.retry_after)}
    raise HTTPException(
        status_code=status_code,
        detail=str(exc),
        headers=headers,
    ) from exc
