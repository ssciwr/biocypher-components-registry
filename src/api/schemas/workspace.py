"""Pydantic schemas for the agentic workspace API contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.core.workspace import client_loop as cl
from src.core.workspace.service import Session

# ===========================================================
# =====================  Input Models =======================
# ===========================================================


class SessionKeyRequest(BaseModel):
    """BYOK credential upload for one session; provide exactly one field."""

    api_key: str | None = None
    auth_token: str | None = None


class MessageCreateRequest(BaseModel):
    """A chat turn submitted to a session."""

    content: str


class FileWriteRequest(BaseModel):
    """Full content of a file write."""

    content: str


# ===========================================================
# =====================  Output Models ======================
# ===========================================================


class ToolDescriptor(BaseModel):
    """One tool available to a session's agent loop."""

    name: str
    description: str


class SessionCreateResponse(BaseModel):
    """Response returned when a workspace session is created."""

    session_id: str
    session_token: str
    model: str
    tools: list[ToolDescriptor]

    @classmethod
    def from_session(cls, session: Session) -> SessionCreateResponse:
        """Build the create-session response from a live session."""
        return cls(
            session_id=session.id,
            session_token=session.token,
            model=cl.MODEL,
            tools=session.tool_defs,
        )


class SessionStateResponse(BaseModel):
    """Point-in-time session state, useful after a client reconnect."""

    session_id: str
    model: str
    has_key: bool
    busy: bool
    error: str | None
    tools: list[ToolDescriptor]

    @classmethod
    def from_session(cls, session: Session) -> SessionStateResponse:
        """Build the session-state response from a live session."""
        return cls(
            session_id=session.id,
            model=cl.MODEL,
            has_key=session.has_key,
            busy=session.busy,
            error=session.error,
            tools=session.tool_defs,
        )


class MessageCreateResponse(BaseModel):
    """Response returned when a chat turn is accepted."""

    turn_id: str


class InterruptResponse(BaseModel):
    """Response returned when a running or queued turn is interrupted."""

    status: str


class FileEntryResponse(BaseModel):
    """One directory entry in a workspace file listing."""

    name: str
    path: str
    is_dir: bool


class FileListResponse(BaseModel):
    """Response returned when listing one workspace directory level."""

    path: str
    entries: list[FileEntryResponse]


class FileContentResponse(BaseModel):
    """Response returned when reading one workspace file."""

    path: str
    content: str
    etag: str


class FileWriteResponse(BaseModel):
    """Response returned when writing one workspace file."""

    path: str
    etag: str


# ===========================================================
# =====================  OpenAPI Helpers =====================
# ===========================================================

WORKSPACE_ERROR_DESCRIPTIONS: dict[int, str] = {
    400: "Invalid input: bad path, empty content, or missing key field",
    401: "Unknown session or invalid session token",
    404: "No such file or directory",
    409: "Conflict: turn running, stale If-Match, filesystem error, "
    "or nothing to interrupt",
    415: "Not a text file",
    428: "No API key set for this session yet",
    502: "MCP server unreachable or the session's MCP connection died",
}


def workspace_error_responses(*codes: int) -> dict[int, dict[str, Any]]:
    """OpenAPI documentation for a workspace route's error status codes."""
    return {code: {"description": WORKSPACE_ERROR_DESCRIPTIONS[code]} for code in codes}
