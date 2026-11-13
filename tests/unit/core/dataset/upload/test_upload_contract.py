from __future__ import annotations

import asyncio
import hashlib
import sys
from pathlib import Path

import pytest

from src.core.dataset import process as process_module
from src.core.dataset.backends.auto_select import AutoDatasetGenerator
from src.core.dataset.process import run_bounded_process
from src.core.dataset.request import GenerationRequest
from src.core.dataset.upload import reconciliation as reconciliation_module
from src.core.dataset.upload.capabilities import validate_capability
from src.core.dataset.upload.errors import UploadSessionError
from src.core.dataset.upload.limits import MAX_ARTIFACT_BYTES, MAX_DIAGNOSTIC_BYTES
from src.core.dataset.upload.models import (
    UploadGenerationOptions,
    UploadInventoryEntry,
)
from src.core.dataset.upload.reconciliation import reconcile_generated_metadata
from src.core.dataset.upload.service import UploadSessionManager


def _entry(
    entry_id: str,
    path: str,
    *,
    size: int = 3,
    mode: str = "complete",
    compression: str | None = None,
    artifact_size: int | None = None,
) -> UploadInventoryEntry:
    logical_format = "tsv" if path.endswith((".tsv", ".tsv.gz")) else "csv"
    if compression == "gzip":
        strategy = f"{logical_format}-gzip-complete-rows-v1"
    else:
        strategy = (
            "complete-file-v1"
            if mode == "complete"
            else f"{logical_format}-complete-rows-v1"
        )
    return UploadInventoryEntry(
        entry_id=entry_id,
        relative_path=path,
        original_size=size,
        logical_format=logical_format,  # type: ignore[arg-type]
        artifact_mode=mode,  # type: ignore[arg-type]
        strategy=strategy,
        declared_artifact_size=size if artifact_size is None else artifact_size,
        compression=compression,  # type: ignore[arg-type]
    )


def test_one_mib_boundary_requires_sampling_only_above_limit() -> None:
    validate_capability(
        logical_format="csv",
        artifact_mode="complete",
        strategy="complete-file-v1",
        original_size=MAX_ARTIFACT_BYTES,
    )
    with pytest.raises(ValueError, match="larger than 1 MiB"):
        validate_capability(
            logical_format="csv",
            artifact_mode="complete",
            strategy="complete-file-v1",
            original_size=MAX_ARTIFACT_BYTES + 1,
        )


def test_gzip_sources_always_require_bounded_sampling() -> None:
    validate_capability(
        logical_format="tsv",
        artifact_mode="sample",
        strategy="tsv-gzip-complete-rows-v1",
        original_size=42,
        compression="gzip",
    )
    with pytest.raises(ValueError, match="must use bounded"):
        validate_capability(
            logical_format="tsv",
            artifact_mode="complete",
            strategy="complete-file-v1",
            original_size=42,
            compression="gzip",
        )


def test_reconciliation_restores_baker_gzip_identity(tmp_path: Path) -> None:
    manager = UploadSessionManager(scratch_root=tmp_path, require_tmpfs=False)

    async def exercise() -> None:
        manager.start()
        entry = _entry(
            "entry-1",
            "nested/people.tsv.gz",
            size=42,
            mode="sample",
            compression="gzip",
        )
        session, _ = await manager.create(
            source_kind="file",
            source_name="people.tsv.gz",
            entries=[entry],
            generation=UploadGenerationOptions(),
        )
        entry.original_sha256 = "a" * 64
        entry.artifact_sha256 = "b" * 64
        reconciled = reconcile_generated_metadata(
            {
                "distribution": [
                    {
                        "@type": "cr:FileObject",
                        "contentUrl": "nested/people.tsv.gz",
                        "encodingFormat": [
                            "text/tab-separated-values",
                            "application/gzip",
                        ],
                        "sha256": entry.artifact_sha256,
                    }
                ]
            },
            session,
        )
        file_object = reconciled["distribution"][0]
        assert file_object["name"] == "people.tsv.gz"
        assert file_object["contentSize"] == "42"
        assert file_object["sha256"] == entry.original_sha256
        assert file_object["encodingFormat"] == [
            "text/tab-separated-values",
            "application/gzip",
        ]
        await manager.shutdown()

    asyncio.run(exercise())


def test_inventory_accepts_1000_files_and_rejects_1001(tmp_path: Path) -> None:
    async def exercise() -> None:
        accepted = UploadSessionManager(
            scratch_root=tmp_path / "accepted", require_tmpfs=False
        )
        accepted.start()
        session, _ = await accepted.create(
            source_kind="folder",
            source_name="dataset",
            entries=[
                _entry(
                    f"e-{index}",
                    f"nested/{index}.csv",
                    size=0 if index == 0 else 3,
                )
                for index in range(1000)
            ],
            generation=UploadGenerationOptions(),
        )
        assert len(session.entries) == 1000
        assert session.entries["e-0"].original_size == 0
        await accepted.shutdown()

        rejected = UploadSessionManager(
            scratch_root=tmp_path / "rejected", require_tmpfs=False
        )
        rejected.start()
        with pytest.raises(UploadSessionError, match="at most 1000"):
            await rejected.create(
                source_kind="folder",
                source_name="dataset",
                entries=[_entry(f"e-{index}", f"{index}.csv") for index in range(1001)],
                generation=UploadGenerationOptions(),
            )

    asyncio.run(exercise())


def test_mixed_plain_and_gzip_folder_reconciles_every_original_file(
    tmp_path: Path,
) -> None:
    manager = UploadSessionManager(scratch_root=tmp_path, require_tmpfs=False)

    async def exercise() -> None:
        manager.start()
        plain = _entry("plain", "tables/people.csv", size=21)
        compressed = _entry(
            "compressed",
            "archives/events.tsv.gz",
            size=42,
            mode="sample",
            compression="gzip",
        )
        session, _ = await manager.create(
            source_kind="folder",
            source_name="dataset",
            entries=[plain, compressed],
            generation=UploadGenerationOptions(),
        )
        plain.original_sha256 = "a" * 64
        plain.artifact_sha256 = plain.original_sha256
        compressed.original_sha256 = "b" * 64
        compressed.artifact_sha256 = "c" * 64

        reconciled = reconcile_generated_metadata(
            {
                "distribution": [
                    {
                        "@type": "cr:FileObject",
                        "contentUrl": "tables/people.csv",
                    },
                    {
                        "@type": "cr:FileObject",
                        "contentUrl": "archives/events.tsv.gz",
                    },
                ]
            },
            session,
        )

        plain_file, compressed_file = reconciled["distribution"]
        assert plain_file["sha256"] == plain.original_sha256
        assert plain_file["encodingFormat"] == "text/csv"
        assert compressed_file["name"] == "events.tsv.gz"
        assert compressed_file["contentSize"] == "42"
        assert compressed_file["sha256"] == compressed.original_sha256
        assert compressed_file["encodingFormat"] == [
            "text/tab-separated-values",
            "application/gzip",
        ]
        assert compressed.artifact_sha256 not in str(reconciled)
        await manager.shutdown()

    asyncio.run(exercise())


def test_artifact_sha_is_verified_but_original_sha_is_reconciled(
    tmp_path: Path,
) -> None:
    async def chunks(value: bytes):
        yield value

    async def exercise() -> None:
        manager = UploadSessionManager(scratch_root=tmp_path, require_tmpfs=False)
        manager.start()
        original_size = MAX_ARTIFACT_BYTES + 1
        entry = _entry(
            "entry-1",
            "nested/data.csv",
            size=original_size,
            mode="sample",
            artifact_size=3,
        )
        entry.content_url = "https://example.org/datasets/data.csv"
        session, _ = await manager.create(
            source_kind="folder",
            source_name="dataset",
            entries=[entry],
            generation=UploadGenerationOptions(),
        )
        artifact = b"a,b"
        artifact_sha = hashlib.sha256(artifact).hexdigest()
        original_sha = "a" * 64
        await manager.upload_artifact(
            session=session,
            entry_id=entry.entry_id,
            body=chunks(artifact),
            content_length=len(artifact),
            artifact_sha256=artifact_sha,
            original_sha256=original_sha,
        )
        document = {
            "@type": "sc:Dataset",
            "url": session.root.as_uri(),
            "distribution": [
                {
                    "@type": "cr:FileObject",
                    "name": "data.csv",
                    "contentUrl": "nested/data.csv",
                    "sha256": artifact_sha,
                    "entryId": "entry-1",
                    "artifactSha256": artifact_sha,
                    "rowCount": 2,
                    "examples": [["a", "b"]],
                }
            ],
        }
        reconciled = reconcile_generated_metadata(document, session)
        file_object = reconciled["distribution"][0]
        assert file_object["sha256"] == original_sha
        assert file_object["contentSize"] == str(original_size)
        assert file_object["contentUrl"] == "https://example.org/datasets/data.csv"
        assert "entryId" not in file_object
        assert "artifactSha256" not in file_object
        assert "rowCount" not in file_object
        assert "examples" not in file_object
        assert "url" not in reconciled
        assert artifact_sha not in str(reconciled)
        root = session.root
        await manager.destroy(session.session_id)
        assert not root.exists()

    asyncio.run(exercise())


def test_nested_duplicate_basenames_require_exact_paths(tmp_path: Path) -> None:
    session_manager = UploadSessionManager(scratch_root=tmp_path, require_tmpfs=False)

    async def exercise() -> None:
        session_manager.start()
        entries = [_entry("one", "a/data.csv"), _entry("two", "b/data.csv")]
        session, _ = await session_manager.create(
            source_kind="folder",
            source_name="dataset",
            entries=entries,
            generation=UploadGenerationOptions(),
        )
        for entry in entries:
            entry.original_sha256 = entry.entry_id[0] * 64
            entry.artifact_sha256 = entry.original_sha256
        ambiguous = {
            "distribution": [
                {"@type": "cr:FileObject", "name": "data.csv"},
                {"@type": "cr:FileObject", "name": "data.csv"},
            ]
        }
        with pytest.raises(UploadSessionError, match="unambiguously"):
            reconcile_generated_metadata(ambiguous, session)
        exact = {
            "distribution": [
                {
                    "@type": "cr:FileObject",
                    "contentUrl": "a/data.csv",
                    "recordCount": 2,
                    "sampleValues": ["private example"],
                },
                {"@type": "cr:FileObject", "contentUrl": "b/data.csv"},
            ]
        }
        reconciled = reconcile_generated_metadata(exact, session)
        assert len(reconciled["distribution"]) == 2
        assert reconciled["distribution"][0]["recordCount"] == 2
        assert "sampleValues" not in reconciled["distribution"][0]
        await session_manager.shutdown()

    asyncio.run(exercise())


def test_reconciliation_rejects_an_oversized_final_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = UploadSessionManager(scratch_root=tmp_path, require_tmpfs=False)

    async def exercise() -> None:
        manager.start()
        entry = _entry("entry-1", "data.csv")
        session, _ = await manager.create(
            source_kind="file",
            source_name="dataset",
            entries=[entry],
            generation=UploadGenerationOptions(),
        )
        entry.original_sha256 = "a" * 64
        entry.artifact_sha256 = entry.original_sha256
        monkeypatch.setattr(reconciliation_module, "MAX_GENERATED_JSON_BYTES", 100)

        with pytest.raises(UploadSessionError, match="response size limit"):
            reconcile_generated_metadata(
                {
                    "description": "x" * 200,
                    "distribution": [
                        {"@type": "cr:FileObject", "contentUrl": "data.csv"}
                    ],
                },
                session,
            )
        await manager.shutdown()

    asyncio.run(exercise())


def test_baker_failure_does_not_invoke_native(monkeypatch: pytest.MonkeyPatch) -> None:
    native_called = False

    def baker_failure(*_args, **_kwargs):
        raise RuntimeError("baker failed")

    def native_generation(*_args, **_kwargs):
        nonlocal native_called
        native_called = True

    monkeypatch.setattr(
        "src.core.dataset.backends.croissant_baker.CroissantBakerGenerator.generate",
        baker_failure,
    )
    monkeypatch.setattr(
        "src.core.dataset.backends.native.NativeDatasetGenerator.generate",
        native_generation,
    )
    with pytest.raises(RuntimeError, match="baker failed"):
        AutoDatasetGenerator().generate(
            GenerationRequest(input_path="data.csv", output_path="out.jsonld")
        )
    assert native_called is False


def test_upload_service_fails_closed_without_tmpfs(tmp_path: Path) -> None:
    async def exercise() -> None:
        manager = UploadSessionManager(scratch_root=tmp_path, require_tmpfs=True)
        manager.start()
        assert manager.enabled is False
        with pytest.raises(UploadSessionError, match="tmpfs"):
            await manager.create(
                source_kind="file",
                source_name="data.csv",
                entries=[_entry("entry-1", "data.csv")],
                generation=UploadGenerationOptions(),
            )

    asyncio.run(exercise())


def test_global_budget_is_reserved_atomically_and_failed_part_is_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def chunks(value: bytes):
        yield value

    async def exercise() -> None:
        monkeypatch.setattr(
            "src.core.dataset.upload.service.MAX_GLOBAL_SCRATCH_BYTES", 3
        )
        manager = UploadSessionManager(scratch_root=tmp_path, require_tmpfs=False)
        manager.start()
        first, _ = await manager.create(
            source_kind="file",
            source_name="one.csv",
            entries=[_entry("one", "one.csv", size=3)],
            generation=UploadGenerationOptions(),
        )
        with pytest.raises(UploadSessionError, match="scratch capacity"):
            await manager.create(
                source_kind="file",
                source_name="two.csv",
                entries=[_entry("two", "two.csv", size=3)],
                generation=UploadGenerationOptions(),
            )
        value = b"abc"
        digest = hashlib.sha256(value).hexdigest()
        await manager.upload_artifact(
            session=first,
            entry_id="one",
            body=chunks(value),
            content_length=3,
            artifact_sha256=digest,
            original_sha256=digest,
        )
        await manager.destroy(first.session_id)
        second, _ = await manager.create(
            source_kind="file",
            source_name="two.csv",
            entries=[_entry("two", "two.csv", size=3)],
            generation=UploadGenerationOptions(),
        )
        with pytest.raises(UploadSessionError, match="verification failed"):
            await manager.upload_artifact(
                session=second,
                entry_id="two",
                body=chunks(value),
                content_length=3,
                artifact_sha256="b" * 64,
                original_sha256="b" * 64,
            )
        assert list(second.root.rglob("*.part-*")) == []
        await manager.shutdown()

    asyncio.run(exercise())


def test_failed_artifact_can_be_retried_only_as_a_complete_body(
    tmp_path: Path,
) -> None:
    async def chunks(*values: bytes):
        for value in values:
            yield value

    async def exercise() -> None:
        manager = UploadSessionManager(scratch_root=tmp_path, require_tmpfs=False)
        manager.start()
        session, _ = await manager.create(
            source_kind="file",
            source_name="data.csv",
            entries=[_entry("entry-1", "data.csv", size=3)],
            generation=UploadGenerationOptions(),
        )
        content = b"abc"
        digest = hashlib.sha256(content).hexdigest()

        with pytest.raises(UploadSessionError, match="byte count"):
            await manager.upload_artifact(
                session=session,
                entry_id="entry-1",
                body=chunks(content[:1]),
                content_length=len(content),
                artifact_sha256=digest,
                original_sha256=digest,
            )

        entry = session.entries["entry-1"]
        assert entry.is_complete is False
        assert entry.uploading is False
        assert session.reserved_bytes == 3
        assert list(session.root.rglob("*.part-*")) == []

        retried = await manager.upload_artifact(
            session=session,
            entry_id="entry-1",
            body=chunks(content[:1], content[1:]),
            content_length=len(content),
            artifact_sha256=digest,
            original_sha256=digest,
        )
        assert retried.is_complete is True
        assert (session.input_root / "data.csv").read_bytes() == content
        await manager.shutdown()

    asyncio.run(exercise())


def test_completed_artifact_replay_is_idempotent_and_conflicts_are_rejected(
    tmp_path: Path,
) -> None:
    async def chunks(value: bytes):
        yield value

    async def exercise() -> None:
        manager = UploadSessionManager(scratch_root=tmp_path, require_tmpfs=False)
        manager.start()
        session, _ = await manager.create(
            source_kind="file",
            source_name="data.csv",
            entries=[_entry("entry-1", "data.csv", size=3)],
            generation=UploadGenerationOptions(),
        )
        content = b"abc"
        digest = hashlib.sha256(content).hexdigest()
        uploaded = await manager.upload_artifact(
            session=session,
            entry_id="entry-1",
            body=chunks(content),
            content_length=len(content),
            artifact_sha256=digest,
            original_sha256=digest,
        )

        replayed = await manager.upload_artifact(
            session=session,
            entry_id="entry-1",
            body=chunks(content),
            content_length=len(content),
            artifact_sha256=digest,
            original_sha256=digest,
        )
        assert replayed is uploaded

        conflicting_digest = hashlib.sha256(b"xyz").hexdigest()
        with pytest.raises(UploadSessionError, match="already uploaded"):
            await manager.upload_artifact(
                session=session,
                entry_id="entry-1",
                body=chunks(b"xyz"),
                content_length=3,
                artifact_sha256=conflicting_digest,
                original_sha256=conflicting_digest,
            )

        assert (session.input_root / "data.csv").read_bytes() == content
        assert session.received_bytes == 3
        assert session.reserved_bytes == 0
        await manager.shutdown()

    asyncio.run(exercise())


def test_shutdown_removes_all_remaining_session_trees(tmp_path: Path) -> None:
    async def exercise() -> None:
        manager = UploadSessionManager(scratch_root=tmp_path, require_tmpfs=False)
        manager.start()
        first, _ = await manager.create(
            source_kind="file",
            source_name="one.csv",
            entries=[_entry("one", "one.csv")],
            generation=UploadGenerationOptions(),
        )
        second, _ = await manager.create(
            source_kind="file",
            source_name="two.csv",
            entries=[_entry("two", "two.csv")],
            generation=UploadGenerationOptions(),
        )
        assert first.root.exists()
        assert second.root.exists()

        await manager.shutdown()

        assert first.root.exists() is False
        assert second.root.exists() is False
        assert list(tmp_path.iterdir()) == []

    asyncio.run(exercise())


def test_generator_process_environment_excludes_application_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    class FakeProcess:
        returncode = 0

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["environment"] = kwargs["env"]
        return FakeProcess()

    monkeypatch.setenv("POSTGRES_PASSWORD", "database-secret")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "api-secret")
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_SECRET", "oauth-secret")
    monkeypatch.setattr(
        "src.core.dataset.process.shutil.which", lambda _: "/usr/bin/prlimit"
    )
    monkeypatch.setattr("src.core.dataset.process.subprocess.Popen", fake_popen)
    monkeypatch.setattr(
        "src.core.dataset.process._drain_process",
        lambda _process: (b"", b"", False),
    )
    result = run_bounded_process(["trusted-generator"], scratch_directory=tmp_path)
    environment = captured["environment"]
    assert result.returncode == 0
    assert isinstance(environment, dict)
    assert "POSTGRES_PASSWORD" not in environment
    assert "ANTHROPIC_API_KEY" not in environment
    assert "GITHUB_OAUTH_CLIENT_SECRET" not in environment
    command = captured["command"]
    assert isinstance(command, list)
    assert command[0] == "/usr/bin/prlimit"
    assert any(value.startswith("--as=") for value in command)
    assert any(value.startswith("--cpu=") for value in command)
    assert any(value.startswith("--fsize=") for value in command)
    assert "--nofile=64:64" in command


def test_generator_process_bounds_stdout_and_stderr(tmp_path: Path) -> None:
    oversized = MAX_DIAGNOSTIC_BYTES * 2
    result = run_bounded_process(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                f"sys.stdout.write('o' * {oversized}); "
                f"sys.stderr.write('e' * {oversized})"
            ),
        ],
        scratch_directory=tmp_path,
    )

    assert result.returncode == 0
    assert len(result.stdout.encode("utf-8")) == MAX_DIAGNOSTIC_BYTES
    assert len(result.stderr.encode("utf-8")) == MAX_DIAGNOSTIC_BYTES


def test_generator_process_enforces_wall_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(process_module, "GENERATOR_TIMEOUT_SECONDS", 0)

    result = run_bounded_process(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        scratch_directory=tmp_path,
    )

    assert result.timed_out is True
    assert result.returncode != 0
