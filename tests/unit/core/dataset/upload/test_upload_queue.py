from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from src.core.dataset.upload.errors import UploadSessionError
from src.core.dataset.upload.models import UploadGenerationOptions, UploadInventoryEntry
from src.core.dataset.upload.service import UploadSessionManager


def _entry(name: str, size: int) -> UploadInventoryEntry:
    return UploadInventoryEntry(
        entry_id=name,
        relative_path=f"{name}.csv",
        original_size=size,
        logical_format="csv",
        artifact_mode="complete",
        strategy="complete-file-v1",
        declared_artifact_size=size,
    )


def test_admission_uses_reserved_bytes_and_releases_them(
    tmp_path: Path, monkeypatch
) -> None:
    async def exercise() -> None:
        monkeypatch.setattr("src.core.dataset.upload.service.MAX_GLOBAL_SCRATCH_BYTES", 10)
        manager = UploadSessionManager(scratch_root=tmp_path, require_tmpfs=False)
        manager.start()
        first, _ = await manager.create(
            source_kind="file", source_name="one", entries=[_entry("one", 6)],
            generation=UploadGenerationOptions(),
        )
        with pytest.raises(UploadSessionError) as error:
            await manager.create(
                source_kind="file", source_name="two", entries=[_entry("two", 5)],
                generation=UploadGenerationOptions(),
            )
        assert error.value.status_code == 429
        assert error.value.retry_after == 15
        await manager.destroy(first.session_id)
        second, _ = await manager.create(
            source_kind="file", source_name="two", entries=[_entry("two", 5)],
            generation=UploadGenerationOptions(),
        )
        assert second.reserved_bytes == 5
        await manager.shutdown()

    asyncio.run(exercise())


def test_many_small_sessions_fit_without_waiting_queue(
    tmp_path: Path, monkeypatch
) -> None:
    async def exercise() -> None:
        monkeypatch.setattr("src.core.dataset.upload.service.MAX_GLOBAL_SCRATCH_BYTES", 100)
        manager = UploadSessionManager(scratch_root=tmp_path, require_tmpfs=False)
        manager.start()
        sessions = []
        for index in range(100):
            session, _ = await manager.create(
                source_kind="file", source_name=str(index),
                entries=[_entry(f"e-{index}", 1)],
                generation=UploadGenerationOptions(),
            )
            sessions.append(session)
        assert len(sessions) == 100
        with pytest.raises(UploadSessionError) as error:
            await manager.create(
                source_kind="file", source_name="overflow",
                entries=[_entry("overflow", 1)], generation=UploadGenerationOptions(),
            )
        assert error.value.status_code == 429
        await manager.shutdown()

    asyncio.run(exercise())
