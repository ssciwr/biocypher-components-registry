"""In-memory models for ephemeral dataset upload sessions."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal


class UploadSessionState(StrEnum):
    """Lifecycle states for a transient upload session."""

    CREATED = "created"
    UPLOADING = "uploading"
    READY = "ready"
    FINALIZE_QUEUED = "finalize_queued"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"
    CLOSING = "closing"


@dataclass(slots=True)
class UploadTerminalResult:
    """Bounded result retained after artifact scratch has been released."""

    value: Any | None = None
    error: str | None = None
    completed_at: float = field(default_factory=time.monotonic)


@dataclass(slots=True)
class UploadInventoryEntry:
    """One original file and its transient server artifact."""

    entry_id: str
    relative_path: str
    original_size: int
    logical_format: Literal["csv", "tsv"]
    artifact_mode: Literal["complete", "sample"]
    strategy: str
    declared_artifact_size: int = 0
    compression: Literal["gzip"] | None = None
    content_url: str | None = None
    original_sha256: str | None = None
    artifact_sha256: str | None = None
    artifact_size: int = 0
    uploading: bool = False

    @property
    def is_complete(self) -> bool:
        """Return whether the server has verified the artifact."""
        return self.artifact_sha256 is not None


@dataclass(slots=True)
class UploadGenerationOptions:
    """User-provided metadata applied to the generated Croissant document."""

    generator: Literal["auto", "croissant-baker", "native"] = "auto"
    validate: bool = True
    name: str | None = None
    description: str | None = None
    url: str | None = None
    license_value: str | None = None
    citation: str | None = None
    dataset_version: str | None = None
    date_published: str | None = None
    creators: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class UploadSession:
    """All transient state for one browser upload workflow."""

    session_id: str
    token_digest: str
    source_kind: Literal["file", "folder"]
    source_name: str
    root: Path
    input_root: Path
    entries: dict[str, UploadInventoryEntry]
    generation: UploadGenerationOptions
    state: UploadSessionState = UploadSessionState.CREATED
    received_bytes: int = 0
    reserved_bytes: int = 0
    active_operations: int = 0
    last_active: float = field(default_factory=time.monotonic)
    created_at: float = field(default_factory=time.monotonic)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    idle_event: asyncio.Event = field(default_factory=asyncio.Event)
    terminal_result: UploadTerminalResult | None = None

    def __post_init__(self) -> None:
        """Mark a newly created session as having no active operation."""
        self.idle_event.set()

    def mark_active(self) -> None:
        """Refresh the monotonic idle timer."""
        self.last_active = time.monotonic()

    @property
    def complete_entries(self) -> int:
        """Count server-verified artifacts."""
        return sum(entry.is_complete for entry in self.entries.values())

    @property
    def is_ready(self) -> bool:
        """Return whether every declared artifact has been verified."""
        return bool(self.entries) and all(
            entry.is_complete for entry in self.entries.values()
        )
