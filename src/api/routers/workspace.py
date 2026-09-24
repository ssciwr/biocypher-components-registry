"""Agentic workspace routes: chat sessions, SSE events, and workspace files.

Mounted under ``settings.agent_api_prefix`` (default ``/agent/api/v1``), kept
distinct from ``settings.api_v1_prefix`` so the workspace service can sit
behind the registry's nginx unchanged. See ``docs/API.md`` for the full
route-level contract (auth, SSE event shapes, error codes).

Auth: all routes require the registry GitHub auth session. Every
``/sessions/{id}/...`` route also requires the session token returned by
``POST /sessions``, either as ``Authorization: Bearer <token>`` or as a
``?token=`` query parameter (the query form exists for browser-native
EventSource, which cannot set headers; prefer the header).
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, Depends, HTTPException
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
from src.core.workspace import client_loop as cl
from src.core.workspace.service import (
    EventStreamAlreadyActive,
    Session,
    SessionLimitError,
    SessionManager,
    SessionStartupError,
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

router = APIRouter()

SessionManagerDep = Annotated[SessionManager, Depends(get_session_manager)]
WorkspaceSessionDep = Annotated[Session, Depends(get_workspace_session)]
CurrentAuthSessionDep = Annotated[AuthSession, Depends(get_current_auth_session)]


def _resolve(session: Session, path: str):
    try:
        return cl.resolve_in_root(path, session.workspace)
    except ValueError as e:
        raise HTTPException(400, str(e))


# Build the ZIP away from the request event loop to avoid potential thread errors/to avoid using sync in an async context which SonarQUbe does not like
def _create_workspace_archive(workspace: Path) -> str:
    with NamedTemporaryFile(suffix=".zip", delete=False) as file:
        archive_path = file.name
        try:
            with ZipFile(file, "w", ZIP_DEFLATED) as archive:
                for path in workspace.rglob("*"):
                    relative = path.relative_to(workspace)
                    if relative.parts[0] in ARCHIVE_EXCLUDED:
                        continue
                    if path.is_file() and not path.is_symlink():
                        archive.write(path, relative)
        except (OSError, RuntimeError):
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
    except SessionLimitError:
        raise HTTPException(
            429, "Too many open workspace sessions; end one and try again."
        )
    except WorkspaceStorageError:
        # Yes it is more specific but is to prevent server crash just ending SSE causing very vague "Network error"
        raise HTTPException(500, "Issue creating workspace session.")
    except SessionStartupError as e:
        raise HTTPException(502, f"could not connect to MCP server: {e}")
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
    if session.busy:
        raise HTTPException(409, "a turn is already running")
    session.busy = True
    turn_id = uuid.uuid4().hex
    session.inbox.put_nowait((turn_id, body.content))
    return MessageCreateResponse(turn_id=turn_id)


@router.post(
    "/sessions/{session_id}/interrupt",
    status_code=202,
    summary="Interrupt the running turn",
    description=(
        "Cancel the running turn, or a turn that was accepted but has not "
        "started yet. History rolls back to the pre-turn snapshot."
    ),
    responses=workspace_error_responses(401, 409),
)
async def interrupt(session_id: str, session: WorkspaceSessionDep) -> InterruptResponse:
    """Interrupt the in-flight or queued turn on one session."""
    if not session.interrupt():
        raise HTTPException(409, "no turn is running")
    return InterruptResponse(status="interrupting")


@router.get(
    "/sessions/{session_id}/events",
    summary="Stream session events",
    description=(
        "Server-sent events for one session: turn lifecycle, streamed text, "
        "tool calls/results, usage, and filesystem changes. See docs/API.md "
        "for the full event catalog."
    ),
    response_class=StreamingResponse,
    responses={
        200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}},
        409: {"description": "An event stream is already active for this session."},
        **workspace_error_responses(401),
    },
)
async def events(
    session_id: str, session: WorkspaceSessionDep, manager: SessionManagerDep
):
    """Stream one session's events as text/event-stream."""
    event_stream = manager.open_event_stream(session)
    # If any SSE stream is open
    if isinstance(event_stream, EventStreamAlreadyActive):
        raise HTTPException(409, "workspace session already has an event stream")
    queue = event_stream

    async def stream():
        try:
            # The session can be deleted between auth and the generator
            # starting; its teardown already published session_closed to
            # the subscribers it knew about, which excludes this one.
            if manager.get(session.id) is not session:
                yield "event: session_closed\ndata: {}\n\n"
                return
            snapshot = {
                "has_key": session.has_key,
                "busy": session.busy,
                "error": session.error,
            }
            yield f"event: session_state\ndata: {json.dumps(snapshot)}\n\n"
            while True:
                # asyncio.timeout rather than wait_for: wait_for's cancel of
                # Queue.get can drop a just-delivered event.
                try:
                    async with asyncio.timeout(HEARTBEAT_SECONDS):
                        event = await queue.get()
                except TimeoutError:
                    yield ": heartbeat\n\n"
                    continue
                yield (
                    f"event: {event['type']}\n"
                    f"id: {event['seq']}\n"
                    f"data: {json.dumps(event['data'])}\n\n"
                )
                if event["type"] == "session_closed":
                    return
        finally:
            manager.close_event_stream(session, queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


# File IO in the routes below is synchronous inside async handlers: it blocks
# # the event loop for the duration of one read/write. Fine at workspace scale
# # (text files, single user per session); revisit with anyio.to_thread if the
# # workspace ever holds large files.


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
    target = _resolve(session, path or ".")
    if not target.is_dir():
        raise HTTPException(404, f"no such directory: {path}")
    entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name))
    return FileListResponse(
        path=path,
        entries=[
            FileEntryResponse(
                name=e.name,
                path=str(e.relative_to(session.workspace)),
                is_dir=e.is_dir(),
            )
            for e in entries
        ],
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
    },
)
# Create .zip for user with the files from the workspace.
async def download_files(session_id: str, session: WorkspaceSessionDep) -> FileResponse:
    try:
        archive_path = await asyncio.to_thread(
            _create_workspace_archive, session.workspace
        )
    except (OSError, RuntimeError):
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
    target = _resolve(session, path)
    if not target.is_file():
        raise HTTPException(404, f"no such file: {path}")
    if target.stat().st_size > MAX_PREVIEW_BYTES:
        raise HTTPException(413, f"file too large to preview: {path}")
    try:
        content = target.read_text()
    except UnicodeDecodeError:
        raise HTTPException(415, f"not a text file: {path}")
    except OSError as e:
        raise HTTPException(409, f"filesystem error: {e}")
    return FileContentResponse(path=path, content=content)
