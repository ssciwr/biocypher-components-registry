from __future__ import annotations

import asyncio
import threading
from pathlib import Path

import pytest

from src.api.routers import dataset_uploads
from src.core.dataset.upload import service as service_module
from src.core.dataset.upload.models import (
    UploadGenerationOptions,
    UploadInventoryEntry,
    UploadSessionState,
    UploadTerminalResult,
)
from src.core.dataset.upload.service import UploadSessionManager


def _entry(entry_id: str = "entry") -> UploadInventoryEntry:
    return UploadInventoryEntry(
        entry_id=entry_id,
        relative_path=f"{entry_id}.csv",
        original_size=1,
        logical_format="csv",
        artifact_mode="complete",
        strategy="complete-file-v1",
        declared_artifact_size=1,
    )


async def _create_ready_session(manager: UploadSessionManager, entry_id: str):
    session, _ = await manager.create(
        source_kind="file",
        source_name=entry_id,
        entries=[_entry(entry_id)],
        generation=UploadGenerationOptions(),
    )
    entry = session.entries[entry_id]
    entry.artifact_sha256 = entry.original_sha256 = entry_id[0] * 64
    session.reserved_bytes = 0
    session.received_bytes = 1
    session.state = UploadSessionState.READY
    return session


def test_generation_waits_for_thread_after_outer_cancellation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def exercise() -> None:
        manager = UploadSessionManager(scratch_root=tmp_path, require_tmpfs=False)
        manager.start()
        session = await _create_ready_session(manager, "alpha")
        started = threading.Event()
        release = threading.Event()
        finished = threading.Event()

        def gated_generation(_session):
            started.set()
            release.wait(timeout=5)
            finished.set()
            return {}, "native", []

        monkeypatch.setattr(
            dataset_uploads, "_generate_and_reconcile", gated_generation
        )
        task = asyncio.create_task(dataset_uploads._run_generation(session))
        assert await asyncio.to_thread(started.wait, 1)

        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        assert not finished.is_set()

        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=1)
        assert finished.is_set()
        await manager.shutdown()

    asyncio.run(exercise())


def test_generation_workers_honor_configured_concurrency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def exercise() -> None:
        monkeypatch.setattr(service_module, "MAX_CONCURRENT_GENERATIONS", 2)
        manager = UploadSessionManager(scratch_root=tmp_path, require_tmpfs=False)
        manager.start()
        sessions = [
            await _create_ready_session(manager, name)
            for name in ("alpha", "beta", "gamma")
        ]
        release = asyncio.Event()
        two_started = asyncio.Event()
        running = 0
        maximum_running = 0

        async def gated_generation(_session):
            nonlocal running, maximum_running
            running += 1
            maximum_running = max(maximum_running, running)
            if running == 2:
                two_started.set()
            try:
                await release.wait()
                return {"ok": True}
            finally:
                running -= 1

        for session in sessions:
            assert await manager.enqueue_generation(session, gated_generation)

        await asyncio.wait_for(two_started.wait(), timeout=1)
        await asyncio.sleep(0)
        assert maximum_running == 2
        assert (
            sum(session.state == UploadSessionState.PROCESSING for session in sessions)
            == 2
        )

        release.set()
        await asyncio.wait_for(manager._generation_queue.join(), timeout=1)
        assert all(session.terminal_result is not None for session in sessions)
        assert (
            sum(session.state == UploadSessionState.COMPLETE for session in sessions)
            == 2
        )
        await manager.shutdown()

    asyncio.run(exercise())


def test_idle_reaper_expires_idle_and_terminal_sessions_but_keeps_active_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def exercise() -> None:
        manager = UploadSessionManager(scratch_root=tmp_path, require_tmpfs=False)
        manager.start()
        idle, _ = await manager.create(
            source_kind="file",
            source_name="idle",
            entries=[_entry("idle")],
            generation=UploadGenerationOptions(),
        )
        active, _ = await manager.create(
            source_kind="file",
            source_name="active",
            entries=[_entry("active")],
            generation=UploadGenerationOptions(),
        )
        terminal, _ = await manager.create(
            source_kind="file",
            source_name="terminal",
            entries=[_entry("terminal")],
            generation=UploadGenerationOptions(),
        )
        idle.state = UploadSessionState.UPLOADING
        idle.last_active = 0
        active.state = UploadSessionState.UPLOADING
        active.last_active = 0
        active.active_operations = 1
        active.idle_event.clear()
        terminal.state = UploadSessionState.COMPLETE
        terminal.terminal_result = UploadTerminalResult(completed_at=0)

        monkeypatch.setattr(service_module.time, "monotonic", lambda: 10_000.0)
        sleep_calls = 0

        async def one_iteration(_seconds: float) -> None:
            nonlocal sleep_calls
            sleep_calls += 1
            if sleep_calls > 1:
                raise asyncio.CancelledError

        monkeypatch.setattr(service_module.asyncio, "sleep", one_iteration)
        with pytest.raises(asyncio.CancelledError):
            await manager.run_idle_reaper()

        assert idle.session_id not in manager._sessions
        assert terminal.session_id not in manager._sessions
        assert active.session_id in manager._sessions
        assert not idle.root.exists()
        assert not terminal.root.exists()
        assert manager._global_bytes == active.reserved_bytes

        active.active_operations = 0
        active.idle_event.set()
        await manager.shutdown()

    asyncio.run(exercise())
