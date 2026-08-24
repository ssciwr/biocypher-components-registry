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
import hashlib
import json
import shutil
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from src.api.dependencies import (
    get_current_auth_session,
    get_session_manager,
    get_workspace_session,
)
from src.api.schemas.workspace import (
    FileContentResponse,
    FileEntryResponse,
    FileListResponse,
    FileWriteRequest,
    FileWriteResponse,
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
    Session,
    SessionManager,
    SessionStartupError,
)

# Seconds between SSE heartbeat comments (keeps proxies from closing the
# stream while the agent is idle).
HEARTBEAT_SECONDS = 15

router = APIRouter()

SessionManagerDep = Annotated[SessionManager, Depends(get_session_manager)]
WorkspaceSessionDep = Annotated[Session, Depends(get_workspace_session)]
CurrentAuthSessionDep = Annotated[AuthSession, Depends(get_current_auth_session)]


def _etag(text: str) -> str:
    return f'"{hashlib.sha256(text.encode()).hexdigest()[:32]}"'


def _resolve(session: Session, path: str):
    try:
        return cl.resolve_in_root(path, session.workspace)
    except ValueError as e:
        raise HTTPException(400, str(e))


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
    responses=workspace_error_responses(401, 502),
)
async def create_session(
    manager: SessionManagerDep,
    auth_session: CurrentAuthSessionDep,
) -> SessionCreateResponse:
    """Create a new workspace session."""
    try:
        session = await manager.create(
            owner_github_user_id=auth_session.github_user_id
        )
    except SessionStartupError as e:
        raise HTTPException(502, f"could not connect to MCP server: {e}")
    return SessionCreateResponse.from_session(session)


@router.get(
    "/sessions/{session_id}",
    summary="Get workspace session state",
    description="Return session state, useful after a client reconnect.",
    responses=workspace_error_responses(401),
)
async def get_session(session: WorkspaceSessionDep) -> SessionStateResponse:
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
    session: WorkspaceSessionDep, manager: SessionManagerDep
) -> None:
    """Delete one workspace session and everything it owns."""
    await manager.delete(session.id)


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
async def set_key(body: SessionKeyRequest, session: WorkspaceSessionDep) -> None:
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
    body: MessageCreateRequest, session: WorkspaceSessionDep
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
async def interrupt(session: WorkspaceSessionDep) -> InterruptResponse:
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
        **workspace_error_responses(401),
    },
)
async def events(session: WorkspaceSessionDep, manager: SessionManagerDep):
    """Stream one session's events as text/event-stream."""
    queue = session.subscribe()

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
            session.unsubscribe(queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


# File IO in the routes below is synchronous inside async handlers: it blocks
# the event loop for the duration of one read/write. Fine at workspace scale
# (text files, single user per session); revisit with anyio.to_thread if the
# workspace ever holds large files.


# ===========================================================
# File Routes (directory pane + editor)
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
async def list_files(session: WorkspaceSessionDep, path: str = "") -> FileListResponse:
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
    "/sessions/{session_id}/file",
    summary="Read a workspace file",
    description="Read one text file's content and ETag for the editor pane.",
    responses=workspace_error_responses(400, 401, 404, 409, 415),
)
async def read_file(path: str, session: WorkspaceSessionDep) -> FileContentResponse:
    """Read one text file from a session's workspace."""
    target = _resolve(session, path)
    if not target.is_file():
        raise HTTPException(404, f"no such file: {path}")
    try:
        content = target.read_text()
    except UnicodeDecodeError:
        raise HTTPException(415, f"not a text file: {path}")
    except OSError as e:
        raise HTTPException(409, f"filesystem error: {e}")
    return FileContentResponse(path=path, content=content, etag=_etag(content))


def _check_if_match(target, if_match: str) -> None:
    """409 when the file changed (or vanished) since the editor loaded it.

    The check is atomic against the agent's file tools (same event loop, no
    await in between) but not against a concurrent run_command subprocess
    writing the same file.
    """
    if not target.is_file():
        raise HTTPException(409, "file no longer exists")
    try:
        current = _etag(target.read_text())
    except UnicodeDecodeError:
        raise HTTPException(415, "not a text file")
    if current != if_match:
        # The agent (or another editor) changed the file since it was loaded;
        # the frontend re-fetches and shows a conflict banner.
        raise HTTPException(409, "file changed since it was loaded")


@router.put(
    "/sessions/{session_id}/file",
    summary="Write a workspace file",
    description=(
        "Create or overwrite one text file. Parent directories are created "
        "as needed. Send If-Match when saving a previously opened file."
    ),
    responses=workspace_error_responses(400, 401, 409),
    # If-Match is read from the raw request (not a Header parameter with a
    # None default), so it is documented here by hand for the OpenAPI schema.
    openapi_extra={
        "parameters": [
            {
                "in": "header",
                "name": "If-Match",
                "schema": {"type": "string"},
                "required": False,
                "description": "ETag from the last GET of this file; the "
                "write is rejected with 409 if the file changed since.",
            }
        ]
    },
)
async def write_file(
    path: str,
    body: FileWriteRequest,
    session: WorkspaceSessionDep,
    request: Request,
) -> FileWriteResponse:
    """Create or overwrite one text file in a session's workspace."""
    if_match = request.headers.get("if-match")
    target = _resolve(session, path)
    if target.is_dir():
        raise HTTPException(409, f"is a directory: {path}")
    try:
        if if_match:
            _check_if_match(target, if_match)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body.content)
    except OSError as e:
        # e.g. a parent component is an existing file, or permissions
        raise HTTPException(409, f"filesystem error: {e}")
    session.publish("fs_changed", paths=[path])
    return FileWriteResponse(path=path, etag=_etag(body.content))


@router.delete(
    "/sessions/{session_id}/file",
    status_code=204,
    summary="Delete a workspace file or directory",
    description="Delete one file or directory (recursively) from the tree pane.",
    responses=workspace_error_responses(400, 401, 404, 409),
)
async def delete_file(path: str, session: WorkspaceSessionDep) -> None:
    """Delete one file or directory from a session's workspace."""
    target = _resolve(session, path)
    if target == session.workspace:
        raise HTTPException(400, "refusing to delete the workspace root")
    try:
        if target.is_dir():
            shutil.rmtree(target)
        elif target.is_file():
            target.unlink()
        else:
            raise HTTPException(404, f"no such file or directory: {path}")
    except OSError as e:
        raise HTTPException(409, f"filesystem error: {e}")
    session.publish("fs_changed", paths=[path])
