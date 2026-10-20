"""Agentic workspace routes: chat sessions, SSE events, and workspace files.

Mounted under ``settings.agent_api_prefix`` (default ``/agent/api/v1``), kept
distinct from ``settings.api_v1_prefix`` so the workspace service can sit
behind the registry's nginx unchanged. See ``docs/API.md`` for the full
route-level contract (auth, SSE event shapes, error codes).

Auth: all routes require the registry GitHub auth session. Every
``/sessions/{id}/...`` route also requires the session token returned by
``POST /sessions`` as ``Authorization: Bearer <token>``. There is no query
parameter form: tokens in URLs end up in proxy access logs.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from tempfile import NamedTemporaryFile
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from starlette.background import BackgroundTask

from src.api.dependencies import (
    get_current_auth_session,
    get_session_manager,
    get_workspace_session,
)
from src.api.schemas.workspace import (
    FileContentResponse,
    FileEntryResponse,
    FileListResponse,
    InterruptResponse,
    MessageCreateRequest,
    MessageCreateResponse,
    SessionCreateResponse,
    SessionKeyRequest,
    SessionStateResponse,
    workspace_error_responses,
)
from src.core.auth.models import AuthSession
from src.core.workspace import workspace_fs as wfs
from src.core.workspace.service import (
    Session,
    SessionLimitError,
    SessionManager,
    SessionPoolExhaustedError,
    SessionStartupError,
    TurnInFlightError,
    WorkspaceStorageError,
)

# Seconds between SSE heartbeat comments (keeps proxies from closing the
# stream while the agent is idle).
HEARTBEAT_SECONDS = 5  # specifically this amount due to this report: https://github.com/enisdenjo/graphql-sse/issues/99

# Tool state in the workspace (session venv, HOME caches), not user files;
# left out of the download.
ARCHIVE_EXCLUDED = {".venv", ".cache"}
# Largest file the preview pane will load.
MAX_PREVIEW_BYTES = 1_000_000
# Largest workspace download (compressed zip size).
MAX_ARCHIVE_BYTES = int(os.getenv("AGENT_MAX_ARCHIVE_BYTES", str(200 * 1024 * 1024)))

logger = logging.getLogger(__name__)

router = APIRouter()


def _sse_frame(event: dict) -> str:
    return (
        f"event: {event['type']}\n"
        f"id: {event['seq']}\n"
        f"data: {json.dumps(event['data'])}\n\n"
    )


SessionManagerDep = Annotated[SessionManager, Depends(get_session_manager)]
WorkspaceSessionDep = Annotated[Session, Depends(get_workspace_session)]
CurrentAuthSessionDep = Annotated[AuthSession, Depends(get_current_auth_session)]


# File errors from the sandbox user's file operations, as HTTP status codes.
FS_ERROR_STATUS = {
    wfs.INVALID_PATH: 400,
    wfs.NOT_FOUND: 404,
    wfs.TOO_LARGE: 413,
    wfs.NOT_TEXT: 415,
}


def _fs_http_error(session: Session, error: wfs.WorkspaceFSError) -> HTTPException:
    status = FS_ERROR_STATUS.get(error.kind)
    if status is not None:
        return HTTPException(status, str(error))
    # Other errors carry the absolute server path. Session id, not the
    # user-supplied path: keeps request input out of the log.
    logger.error(
        "workspace file operation failed: session_id=%s: %s", session.id, error
    )
    return HTTPException(409, "filesystem error in the workspace")


async def _create_workspace_archive(session: Session) -> str:
    """Zip the workspace into a temp file owned by this process; return its path."""
    with NamedTemporaryFile(suffix=".zip", delete=False) as file:
        archive_path = file.name
        try:
            await session.fs.archive(file, ARCHIVE_EXCLUDED, MAX_ARCHIVE_BYTES)
        except BaseException:
            os.unlink(archive_path)
            raise
    return archive_path


# ===========================================================
# Session Lifecycle Routes
# ===========================================================


@router.post(
    "/sessions",
    status_code=201,
    summary="Create a workspace session",
    description=(
        "Allocate a workspace directory and open the MCP connection for a new "
        "agentic workspace session."
    ),
    responses=workspace_error_responses(401, 429, 500, 502),
)
async def create_session(
    manager: SessionManagerDep,
    auth_session: CurrentAuthSessionDep,
) -> SessionCreateResponse:
    """Create a new workspace session."""
    try:
        session = await manager.create(owner_github_user_id=auth_session.github_user_id)
    except SessionPoolExhaustedError:
        raise HTTPException(
            429, "The workspace service is at capacity; try again later."
        )
    except SessionLimitError:
        raise HTTPException(
            429, "Too many open workspace sessions; end one and try again."
        )
    except WorkspaceStorageError:
        # Yes it is more specific but is to prevent server crash just ending SSE causing very vague "Network error"
        raise HTTPException(500, "Issue creating workspace session.")
    except SessionStartupError:
        # Details are logged by the session actor.
        raise HTTPException(502, "could not connect to MCP server")
    return SessionCreateResponse.from_session(session)


@router.get(
    "/sessions/{session_id}",
    summary="Get workspace session state",
    description="Return session state, useful after a client reconnect.",
    responses=workspace_error_responses(401),
)
async def get_session(
    session_id: str, session: WorkspaceSessionDep
) -> SessionStateResponse:
    """Return the current state of one workspace session."""
    return SessionStateResponse.from_session(session)


@router.delete(
    "/sessions/{session_id}",
    status_code=204,
    summary="End a workspace session",
    description=(
        "Close the MCP connection, drop the history, and destroy the "
        "workspace directory and stored key."
    ),
    responses=workspace_error_responses(401),
)
async def delete_session(
    session_id: str, session: WorkspaceSessionDep, manager: SessionManagerDep
) -> None:
    """Delete one workspace session and everything it owns."""
    await manager.delete(session_id)


@router.post(
    "/sessions/{session_id}/key",
    status_code=204,
    summary="Attach a BYOK credential to a session",
    description=(
        "Store the user's Anthropic API key or auth token for this session "
        "only. Never send credentials as a chat message."
    ),
    responses=workspace_error_responses(400, 401),
)
async def set_key(
    session_id: str, body: SessionKeyRequest, session: WorkspaceSessionDep
) -> None:
    """Attach a BYOK Anthropic credential to one session."""
    if not body.api_key and not body.auth_token:
        raise HTTPException(400, "provide api_key or auth_token")
    session.set_key(body.api_key, body.auth_token)


# ===========================================================
# Chat Routes
# ===========================================================


@router.post(
    "/sessions/{session_id}/messages",
    status_code=202,
    summary="Send a chat message",
    description=(
        "Append a user turn and start the tool loop. Returns immediately; "
        "progress arrives on the events stream."
    ),
    responses=workspace_error_responses(400, 401, 409, 428, 502),
)
async def post_message(
    session_id: str, body: MessageCreateRequest, session: WorkspaceSessionDep
) -> MessageCreateResponse:
    """Start a new chat turn on one session."""
    if session.error:
        raise HTTPException(502, f"session is unusable: {session.error}")
    if not session.has_key:
        raise HTTPException(428, "no API key set for this session; POST .../key first")
    if not body.content.strip():
        raise HTTPException(400, "content must not be empty")
    try:
        turn_id = session.submit(body.content)
    except TurnInFlightError:
        raise HTTPException(409, "a turn is already running") from None
    return MessageCreateResponse(turn_id=turn_id)


@router.post(
    "/sessions/{session_id}/interrupt",
    status_code=202,
    summary="Interrupt the running turn",
    description=(
        "Cancel the running turn. History rolls back to the pre-turn snapshot."
    ),
    responses=workspace_error_responses(401, 409),
)
async def interrupt(session_id: str, session: WorkspaceSessionDep) -> InterruptResponse:
    """Interrupt the in-flight turn on one session."""
    if not session.interrupt():
        raise HTTPException(409, "no turn is running")
    return InterruptResponse(status="interrupting")


def _parse_last_event_id(header: str | None) -> int | None:
    """Last-Event-ID as an event seq; anything unparsable means no replay."""
    try:
        return int(header) if header is not None else None
    except ValueError:
        return None


async def _event_stream(
    manager: SessionManager,
    session: Session,
    queue: asyncio.Queue,
    backlog: list[dict],
):
    """SSE body: state snapshot, replayed backlog, then live events."""
    try:
        # The session can be deleted between auth and the generator starting;
        # its teardown already published session_closed to the subscribers it
        # knew about, which excludes this one.
        if manager.get(session.id) is not session:
            yield "event: session_closed\ndata: {}\n\n"
            return
        snapshot = {
            "has_key": session.has_key,
            "busy": session.busy,
            "error": session.error,
        }
        yield f"event: session_state\ndata: {json.dumps(snapshot)}\n\n"
        for event in backlog:
            yield _sse_frame(event)
        while True:
            # asyncio.timeout rather than wait_for: wait_for's cancel of
            # Queue.get can drop a just-delivered event.
            try:
                async with asyncio.timeout(HEARTBEAT_SECONDS):
                    event = await queue.get()
            except TimeoutError:
                yield ": heartbeat\n\n"
                continue
            if event is None:
                # Replaced by a newer stream for this session.
                return
            yield _sse_frame(event)
            if event["type"] == "session_closed":
                return
    finally:
        manager.close_event_stream(session, queue)


@router.get(
    "/sessions/{session_id}/events",
    summary="Stream session events",
    description=(
        "Server-sent events for one session: turn lifecycle, streamed text, "
        "tool calls/results, usage, and filesystem changes. See docs/API.md "
        "for the full event catalog. On reconnect, send Last-Event-ID to "
        "replay missed events; a new stream replaces an open one."
    ),
    response_class=StreamingResponse,
    responses={
        200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}},
        **workspace_error_responses(401),
    },
)
async def events(
    session_id: str,
    session: WorkspaceSessionDep,
    manager: SessionManagerDep,
    last_event_id: Annotated[str | None, Header()] = None,
):
    """Stream one session's events as text/event-stream."""
    queue, backlog = manager.open_event_stream(
        session, _parse_last_event_id(last_event_id)
    )
    return StreamingResponse(
        _event_stream(manager, session, queue, backlog),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


# File IO in the routes below runs as the session's sandbox user (see
# workspace_fs): the API user cannot read workspaces itself.


# ===========================================================
# File Routes (directory pane + readable field contents preview pane)
# ===========================================================


@router.get(
    "/sessions/{session_id}/files",
    summary="List a workspace directory",
    description=(
        "List one directory level (directories first, then files, both "
        "sorted). Omit path (or pass an empty string) for the workspace root."
    ),
    responses=workspace_error_responses(400, 401, 404),
)
async def list_files(
    session_id: str, session: WorkspaceSessionDep, path: str = ""
) -> FileListResponse:
    """List one directory level of a session's workspace."""
    try:
        entries = await session.fs.list_dir(path or ".")
    except wfs.WorkspaceFSError as e:
        raise _fs_http_error(session, e) from None
    return FileListResponse(
        path=path,
        entries=[FileEntryResponse(**e) for e in entries],
    )


@router.get(
    "/sessions/{session_id}/download",
    response_class=FileResponse,
    responses={
        200: {
            "content": {
                "application/zip": {"schema": {"type": "string", "format": "binary"}}
            }
        },
        409: {"description": "The workspace download could not be prepared."},
        413: {"description": "The workspace archive exceeds the download limit."},
    },
)
# Create .zip for user with the files from the workspace.
async def download_files(session_id: str, session: WorkspaceSessionDep) -> FileResponse:
    try:
        archive_path = await _create_workspace_archive(session)
    except wfs.WorkspaceFSError as e:
        if e.kind == wfs.TOO_LARGE:
            raise HTTPException(413, "Workspace too large to download.") from None
        logger.error("workspace download failed: session_id=%s: %s", session.id, e)
        raise HTTPException(409, "Could not prepare workspace download.") from None
    except OSError:
        logger.exception("workspace download failed: session_id=%s", session.id)
        raise HTTPException(409, "Could not prepare workspace download.") from None
    return FileResponse(
        archive_path,
        background=BackgroundTask(os.unlink, archive_path),
        filename="workspace.zip",
        media_type="application/zip",
    )


@router.get(
    "/sessions/{session_id}/file",
    summary="Read a workspace file",
    description="Read one text file's content for the preview pane.",
    responses=workspace_error_responses(400, 401, 404, 409, 413, 415),
)
async def read_file(
    session_id: str, path: str, session: WorkspaceSessionDep
) -> FileContentResponse:
    """Read one text file from a session's workspace."""
    try:
        content = await session.fs.read_text(path, max_bytes=MAX_PREVIEW_BYTES)
    except wfs.WorkspaceFSError as e:
        raise _fs_http_error(session, e) from None
    return FileContentResponse(path=path, content=content)
