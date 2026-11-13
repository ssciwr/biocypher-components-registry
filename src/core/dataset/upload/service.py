"""Lifecycle service for short-lived, RAM-backed upload sessions."""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import secrets
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import BinaryIO

from src.core.dataset.upload.capabilities import validate_entry_capability
from src.core.dataset.upload.errors import UploadSessionError
from src.core.dataset.upload.hashing import normalize_sha256
from src.core.dataset.upload.limits import (
    MAX_ACTIVE_SESSIONS,
    MAX_ARTIFACT_BYTES,
    MAX_CONCURRENT_GENERATIONS,
    MAX_GLOBAL_SCRATCH_BYTES,
    MAX_SESSION_ARTIFACT_BYTES,
    MAX_TERMINAL_RESULTS,
    REAPER_INTERVAL_SECONDS,
    RESULT_TTL_SECONDS,
    SESSION_IDLE_TTL_SECONDS,
    SESSION_START_TTL_SECONDS,
    UPLOAD_SCRATCH_ROOT,
)
from src.core.dataset.upload.models import (
    UploadGenerationOptions,
    UploadInventoryEntry,
    UploadSession,
    UploadSessionState,
    UploadTerminalResult,
)
from src.core.dataset.upload.paths import normalize_relative_path, validate_unique_paths
from src.core.dataset.upload.scratch import prepare_scratch_root, remove_scratch_tree

_ENTRY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


class UploadSessionManager:
    """Own in-memory session state and RAM-backed artifact accounting."""

    def __init__(
        self,
        *,
        scratch_root: Path = UPLOAD_SCRATCH_ROOT,
        require_tmpfs: bool = True,
    ) -> None:
        self.scratch_root = scratch_root
        self.require_tmpfs = require_tmpfs
        self.enabled = False
        self.disabled_reason = "Upload service has not started."
        self._sessions: dict[str, UploadSession] = {}
        self._global_bytes = 0
        self._lock = asyncio.Lock()
        self.generation_semaphore = asyncio.Semaphore(MAX_CONCURRENT_GENERATIONS)
        self._generation_queue: asyncio.Queue[
            tuple[UploadSession, Callable[[UploadSession], Awaitable[object]]]
        ] = asyncio.Queue()
        self._generation_worker: asyncio.Task[None] | None = None

    def start(self) -> None:
        """Verify scratch storage and remove abandoned process-local data."""
        enabled, reason = prepare_scratch_root(
            self.scratch_root, require_tmpfs=self.require_tmpfs
        )
        self.enabled = enabled
        self.disabled_reason = reason
        if enabled:
            for child in self.scratch_root.iterdir():
                remove_scratch_tree(child)

    async def shutdown(self) -> None:
        """Destroy every session and its artifacts during application shutdown."""
        if self._generation_worker is not None:
            self._generation_worker.cancel()
            with suppress(asyncio.CancelledError):
                await self._generation_worker
            self._generation_worker = None
        async with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
            self._global_bytes = 0
            for session in sessions:
                session.state = UploadSessionState.CLOSING
        await asyncio.gather(*(self._close_and_remove(item) for item in sessions))

    async def run_idle_reaper(self) -> None:
        """Periodically expire sessions that have no operation in progress."""
        while True:
            await asyncio.sleep(REAPER_INTERVAL_SECONDS)
            cutoff = time.monotonic() - SESSION_IDLE_TTL_SECONDS
            now = time.monotonic()
            async with self._lock:
                expired = [
                    item.session_id
                    for item in self._sessions.values()
                    if item.active_operations == 0
                    and item.state
                    in {
                        UploadSessionState.CREATED,
                        UploadSessionState.UPLOADING,
                        UploadSessionState.READY,
                    }
                    and (
                        (
                            item.state == UploadSessionState.CREATED
                            and item.created_at < now - SESSION_START_TTL_SECONDS
                        )
                        or (
                            item.state != UploadSessionState.CREATED
                            and item.last_active < cutoff
                        )
                    )
                ]
                expired_results = [
                    item.session_id
                    for item in self._sessions.values()
                    if item.terminal_result is not None
                    and item.terminal_result.completed_at < now - RESULT_TTL_SECONDS
                ]
            for session_id in expired:
                await self.destroy(session_id)
            for session_id in expired_results:
                await self.destroy(session_id)

    async def create(
        self,
        *,
        source_kind: str,
        source_name: str,
        entries: Iterable[UploadInventoryEntry],
        generation: UploadGenerationOptions,
    ) -> tuple[UploadSession, str]:
        """Validate an inventory and allocate its isolated scratch directory."""
        self._require_enabled()
        inventory = list(entries)
        self._validate_request(source_kind, inventory)
        async with self._lock:
            if len(self._artifact_sessions()) >= MAX_ACTIVE_SESSIONS:
                raise UploadSessionError(
                    "Upload capacity is currently busy. Try again shortly.",
                    status_code=429,
                    retry_after=15,
                )
            requested_bytes = sum(entry.declared_artifact_size for entry in inventory)
            if requested_bytes > MAX_SESSION_ARTIFACT_BYTES:
                raise UploadSessionError(
                    "The session artifact budget was exceeded.", status_code=413
                )
            if self._global_bytes + requested_bytes > MAX_GLOBAL_SCRATCH_BYTES:
                raise UploadSessionError(
                    "Upload scratch capacity is currently busy. Try again shortly.",
                    status_code=429,
                    retry_after=15,
                )
            session, token = self._create_locked(
                source_kind, source_name, inventory, generation
            )
            session.reserved_bytes = requested_bytes
            self._global_bytes += requested_bytes
            return session, token

    def _validate_request(
        self, source_kind: str, inventory: list[UploadInventoryEntry]
    ) -> None:
        if source_kind not in {"file", "folder"}:
            raise UploadSessionError("source_kind must be 'file' or 'folder'.")
        if not inventory:
            raise UploadSessionError("At least one source file is required.")
        from src.core.dataset.upload.limits import MAX_FILES_PER_SOURCE

        if len(inventory) > MAX_FILES_PER_SOURCE:
            raise UploadSessionError(
                f"A source may contain at most {MAX_FILES_PER_SOURCE} files.",
                status_code=413,
            )
        if source_kind == "file" and len(inventory) != 1:
            raise UploadSessionError("A file source must contain exactly one entry.")

        normalized_paths: list[str] = []
        entry_map: dict[str, UploadInventoryEntry] = {}
        for entry in inventory:
            if not _ENTRY_ID.fullmatch(entry.entry_id):
                raise UploadSessionError(f"Invalid entry ID: {entry.entry_id!r}.")
            if entry.entry_id in entry_map:
                raise UploadSessionError(f"Duplicate entry ID: {entry.entry_id!r}.")
            entry.relative_path = normalize_relative_path(entry.relative_path)
            validate_entry_capability(entry)
            normalized_paths.append(entry.relative_path)
            entry_map[entry.entry_id] = entry
        validate_unique_paths(normalized_paths)

    def _create_locked(
        self,
        source_kind: str,
        source_name: str,
        inventory: list[UploadInventoryEntry],
        generation: UploadGenerationOptions,
    ) -> tuple[UploadSession, str]:
        entry_map = {entry.entry_id: entry for entry in inventory}
        session_id = secrets.token_urlsafe(18)
        token = secrets.token_urlsafe(32)
        root = self.scratch_root / session_id
        input_root = root / "input"
        session = UploadSession(
            session_id=session_id,
            token_digest=_token_digest(token),
            source_kind=source_kind,  # type: ignore[arg-type]
            source_name=source_name.strip() or "dataset",
            root=root,
            input_root=input_root,
            entries=entry_map,
            generation=generation,
        )
        self._sessions[session_id] = session
        try:
            input_root.mkdir(parents=True, mode=0o700)
        except BaseException:
            self._sessions.pop(session_id, None)
            raise
        return session, token

    def authorize(self, session_id: str, token: str) -> UploadSession:
        """Return a session only when its unlogged bearer capability matches."""
        session = self._sessions.get(session_id)
        if session is None or not secrets.compare_digest(
            session.token_digest, _token_digest(token)
        ):
            raise UploadSessionError(
                "Unknown upload session or invalid session token.", status_code=401
            )
        return session

    async def upload_artifact(
        self,
        *,
        session: UploadSession,
        entry_id: str,
        body: AsyncIterator[bytes],
        content_length: int,
        artifact_sha256: str,
        original_sha256: str,
    ) -> UploadInventoryEntry:
        """Stream and verify one complete artifact without multipart spooling."""
        entry, artifact_sha256, original_sha256 = self._validate_artifact_upload(
            session=session,
            entry_id=entry_id,
            content_length=content_length,
            artifact_sha256=artifact_sha256,
            original_sha256=original_sha256,
        )

        async with self.operation(session):
            await self._reserve(session, entry)
            completed = self._completed_upload(
                entry, content_length, artifact_sha256, original_sha256
            )
            if completed is not None:
                return completed

            destination = session.input_root / entry.relative_path
            try:
                count = await self._write_verified_artifact(
                    body=body,
                    destination=destination,
                    content_length=content_length,
                    artifact_sha256=artifact_sha256,
                )
            except BaseException:
                await self._reset_failed_upload(session, entry)
                raise

            await self._commit_artifact_upload(
                session=session,
                entry=entry,
                count=count,
                artifact_sha256=artifact_sha256,
                original_sha256=original_sha256,
            )
            session.mark_active()
            return entry

    def _validate_artifact_upload(
        self,
        *,
        session: UploadSession,
        entry_id: str,
        content_length: int,
        artifact_sha256: str,
        original_sha256: str,
    ) -> tuple[UploadInventoryEntry, str, str]:
        """Normalize identity headers and validate immutable upload declarations."""
        artifact_sha256 = normalize_sha256(
            artifact_sha256, field_name="artifact SHA-256"
        )
        original_sha256 = normalize_sha256(
            original_sha256, field_name="original SHA-256"
        )
        if content_length < 0 or content_length > MAX_ARTIFACT_BYTES:
            raise UploadSessionError(
                f"Artifacts may not exceed {MAX_ARTIFACT_BYTES} bytes.", status_code=413
            )
        entry = session.entries.get(entry_id)
        if entry is None:
            raise UploadSessionError(
                "The inventory entry does not exist.", status_code=404
            )
        if content_length != entry.declared_artifact_size:
            raise UploadSessionError(
                "Artifact size does not match the reserved size.", status_code=409
            )
        if entry.artifact_mode == "complete":
            self._validate_complete_artifact(
                entry, content_length, artifact_sha256, original_sha256
            )
        return entry, artifact_sha256, original_sha256

    @staticmethod
    def _validate_complete_artifact(
        entry: UploadInventoryEntry,
        content_length: int,
        artifact_sha256: str,
        original_sha256: str,
    ) -> None:
        if content_length != entry.original_size:
            raise UploadSessionError(
                "A complete artifact must match the declared original size."
            )
        if not secrets.compare_digest(artifact_sha256, original_sha256):
            raise UploadSessionError(
                "A complete artifact must match the original SHA-256."
            )

    @staticmethod
    def _completed_upload(
        entry: UploadInventoryEntry,
        content_length: int,
        artifact_sha256: str,
        original_sha256: str,
    ) -> UploadInventoryEntry | None:
        """Return an identical completed upload or reject conflicting replay."""
        if not entry.is_complete:
            return None
        if (
            entry.artifact_sha256 == artifact_sha256
            and entry.original_sha256 == original_sha256
            and entry.artifact_size == content_length
        ):
            return entry
        raise UploadSessionError("The entry was already uploaded.", status_code=409)

    @staticmethod
    async def _write_verified_artifact(
        *,
        body: AsyncIterator[bytes],
        destination: Path,
        content_length: int,
        artifact_sha256: str,
    ) -> int:
        """Stream, bound, verify, and atomically publish one artifact body."""
        part = destination.with_name(destination.name + f".part-{secrets.token_hex(6)}")
        count = 0
        digest = hashlib.sha256()
        try:
            await asyncio.to_thread(
                destination.parent.mkdir, parents=True, exist_ok=True
            )
            handle = await asyncio.to_thread(_open_exclusive_binary, part)
            try:
                async for chunk in body:
                    count += len(chunk)
                    if count > content_length or count > MAX_ARTIFACT_BYTES:
                        raise UploadSessionError(
                            "Artifact byte count exceeds the declared size.",
                            status_code=413,
                        )
                    digest.update(chunk)
                    await asyncio.to_thread(handle.write, chunk)
                await asyncio.to_thread(_flush_and_sync, handle)
            finally:
                await asyncio.to_thread(handle.close)
            if count != content_length:
                raise UploadSessionError(
                    "Artifact byte count does not match Content-Length."
                )
            if not secrets.compare_digest(digest.hexdigest(), artifact_sha256):
                raise UploadSessionError("Artifact SHA-256 verification failed.")
            await asyncio.to_thread(os.replace, part, destination)
            return count
        except BaseException:
            await asyncio.to_thread(_remove_partial_file, part)
            raise

    @staticmethod
    async def _commit_artifact_upload(
        *,
        session: UploadSession,
        entry: UploadInventoryEntry,
        count: int,
        artifact_sha256: str,
        original_sha256: str,
    ) -> None:
        """Commit verified identity and move bytes from reserved to received."""
        async with session.lock:
            entry.artifact_size = count
            entry.artifact_sha256 = artifact_sha256
            entry.original_sha256 = original_sha256
            entry.uploading = False
            session.reserved_bytes -= count
            session.received_bytes += count
            session.state = (
                UploadSessionState.READY
                if session.is_ready
                else UploadSessionState.UPLOADING
            )

    async def begin_processing(self, session: UploadSession) -> None:
        """Atomically require a complete inventory and lock finalization."""
        async with session.lock:
            if session.state in {
                UploadSessionState.FINALIZE_QUEUED,
                UploadSessionState.PROCESSING,
                UploadSessionState.COMPLETE,
                UploadSessionState.FAILED,
            }:
                return
            if not session.is_ready:
                raise UploadSessionError(
                    "Every inventory entry must be uploaded first.", status_code=409
                )
            session.state = UploadSessionState.FINALIZE_QUEUED
            session.mark_active()

    async def enqueue_generation(
        self,
        session: UploadSession,
        callback: Callable[[UploadSession], Awaitable[object]],
    ) -> bool:
        """Atomically enqueue the session once; repeated finalization is a no-op."""
        async with session.lock:
            if session.state in {
                UploadSessionState.FINALIZE_QUEUED,
                UploadSessionState.PROCESSING,
                UploadSessionState.COMPLETE,
                UploadSessionState.FAILED,
            }:
                return False
            if not session.is_ready:
                raise UploadSessionError(
                    "Every inventory entry must be uploaded first.", status_code=409
                )
            session.state = UploadSessionState.FINALIZE_QUEUED
            session.mark_active()
        await self._generation_queue.put((session, callback))
        if self._generation_worker is None or self._generation_worker.done():
            self._generation_worker = asyncio.create_task(self._run_generation_worker())
        return True

    async def _run_generation_worker(self) -> None:
        while True:
            session, callback = await self._generation_queue.get()
            try:
                async with session.lock:
                    if session.state != UploadSessionState.FINALIZE_QUEUED:
                        continue
                    session.state = UploadSessionState.PROCESSING
                try:
                    value = await callback(session)
                    result = UploadTerminalResult(value=value)
                    state = UploadSessionState.COMPLETE
                except Exception:
                    result = UploadTerminalResult(
                        error="Dataset generation failed. Verify the selected CSV/TSV source and metadata."
                    )
                    state = UploadSessionState.FAILED
                await self._release_artifacts(session)
                async with session.lock:
                    session.terminal_result = result
                    session.state = state
                await self._trim_terminal_results()
            finally:
                self._generation_queue.task_done()

    async def _release_artifacts(self, session: UploadSession) -> None:
        async with self._lock:
            self._global_bytes = max(
                0, self._global_bytes - session.received_bytes - session.reserved_bytes
            )
            session.received_bytes = session.reserved_bytes = 0
        await self._remove_session_tree(session)

    async def _trim_terminal_results(self) -> None:
        async with self._lock:
            terminal = sorted(
                (s for s in self._sessions.values() if s.terminal_result is not None),
                key=lambda s: s.terminal_result.completed_at,  # type: ignore[union-attr]
            )
            expired = [s.session_id for s in terminal[:-MAX_TERMINAL_RESULTS]]
        for session_id in expired:
            await self.destroy(session_id)

    def _artifact_sessions(self) -> list[UploadSession]:
        return [
            s
            for s in self._sessions.values()
            if s.terminal_result is None and s.state != UploadSessionState.CLOSING
        ]

    async def destroy(self, session_id: str) -> None:
        """Forget one session and remove all partial and completed artifacts."""
        async with self._lock:
            session = self._sessions.pop(session_id, None)
            if session is None:
                return
            self._global_bytes = max(
                0,
                self._global_bytes - session.received_bytes - session.reserved_bytes,
            )
            session.state = UploadSessionState.CLOSING
        await self._close_and_remove(session)

    @asynccontextmanager
    async def operation(self, session: UploadSession):
        """Protect a session from idle expiry for the duration of one request."""
        async with session.lock:
            if session.state == UploadSessionState.CLOSING:
                raise UploadSessionError(
                    "The upload session is closing.", status_code=410
                )
            session.active_operations += 1
            session.idle_event.clear()
            session.mark_active()
        try:
            yield
        finally:
            async with session.lock:
                session.active_operations = max(0, session.active_operations - 1)
                if session.active_operations == 0:
                    session.idle_event.set()
                session.mark_active()

    async def _reserve(
        self,
        session: UploadSession,
        entry: UploadInventoryEntry,
    ) -> None:
        async with self._lock, session.lock:
            if session.state in {
                UploadSessionState.FINALIZE_QUEUED,
                UploadSessionState.PROCESSING,
                UploadSessionState.COMPLETE,
                UploadSessionState.FAILED,
                UploadSessionState.CLOSING,
            }:
                raise UploadSessionError(
                    "The session no longer accepts artifacts.", status_code=409
                )
            if entry.uploading:
                raise UploadSessionError(
                    "This entry is already being uploaded.", status_code=409
                )
            if entry.is_complete:
                return
            entry.uploading = True
            session.state = UploadSessionState.UPLOADING

    async def _reset_failed_upload(
        self,
        session: UploadSession,
        entry: UploadInventoryEntry,
    ) -> None:
        async with self._lock, session.lock:
            if entry.uploading:
                entry.uploading = False
                session.state = (
                    UploadSessionState.READY
                    if session.is_ready
                    else UploadSessionState.UPLOADING
                )

    async def _remove_session_tree(self, session: UploadSession) -> None:
        await asyncio.to_thread(remove_scratch_tree, session.root)

    async def _close_and_remove(self, session: UploadSession) -> None:
        await session.idle_event.wait()
        await self._remove_session_tree(session)

    def _require_enabled(self) -> None:
        if not self.enabled:
            raise UploadSessionError(
                self.disabled_reason or "Ephemeral upload scratch is unavailable.",
                status_code=503,
            )


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _open_exclusive_binary(path: Path) -> BinaryIO:
    """Open a new partial artifact from a worker thread."""
    return path.open("xb")


def _flush_and_sync(handle: BinaryIO) -> None:
    """Flush Python and kernel buffers from a worker thread."""
    handle.flush()
    os.fsync(handle.fileno())


def _remove_partial_file(path: Path) -> None:
    """Best-effort removal for a failed partial artifact."""
    with suppress(OSError):
        path.unlink()
