from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.registration.models import RegistrationStatus
from src.core.registration.errors import DuplicateRegistrationError
from src.core.registration.service import (
    finish_registration,
    refresh_active_registrations,
    revalidate_registration,
    submit_registration,
)
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore


def _valid_adapter_document() -> dict:
    return {
        "@context": {
            "@language": "en",
            "@vocab": "https://schema.org/",
            "citeAs": "cr:citeAs",
            "column": "cr:column",
            "conformsTo": "dct:conformsTo",
            "cr": "http://mlcommons.org/croissant/",
            "dataType": {"@id": "cr:dataType", "@type": "@vocab"},
            "dct": "http://purl.org/dc/terms/",
            "examples": {"@id": "cr:examples", "@type": "@json"},
            "extract": "cr:extract",
            "field": "cr:field",
            "fileObject": "cr:fileObject",
            "recordSet": "cr:recordSet",
            "sc": "https://schema.org/",
            "source": "cr:source",
        },
        "@type": "SoftwareSourceCode",
        "@id": "example-adapter",
        "name": "Example Adapter",
        "description": "Adapter description",
        "conformsTo": "https://bioschemas.org/profiles/ComputationalTool/1.0-RELEASE/",
        "version": "1.0.0",
        "license": "https://opensource.org/licenses/MIT",
        "codeRepository": "https://example.org/repo",
        "programmingLanguage": "Python",
        "targetProduct": "BioCypher",
        "creator": [
            {
                "@type": "sc:Person",
                "name": "Example Creator",
                "affiliation": "SSC",
                "identifier": "https://orcid.org/0000-0000-0000-0000",
            }
        ],
        "keywords": ["adapter", "biocypher"],
        "hasPart": [
            {
                "@type": "sc:Dataset",
                "name": "Example dataset",
                "description": "Example dataset",
                "conformsTo": "http://mlcommons.org/croissant/1.0",
                "citeAs": "https://example.org/dataset",
                "creator": [{"@type": "sc:Person", "name": "Example Creator"}],
                "datePublished": "2024-01-01T00:00:00",
                "license": "https://opensource.org/licenses/MIT",
                "url": "https://example.org/dataset",
                "version": "1.0.0",
                "distribution": [
                    {
                        "@id": "file-1",
                        "@type": "cr:FileObject",
                        "name": "data.csv",
                        "contentUrl": "data.csv",
                        "encodingFormat": "text/csv",
                        "sha256": "abc123",
                    }
                ],
                "recordSet": [
                    {
                        "@id": "rs-1",
                        "@type": "cr:RecordSet",
                        "name": "records",
                        "field": [
                            {
                                "@id": "rs-1/id",
                                "@type": "cr:Field",
                                "name": "id",
                                "description": "Column 'id' from data.csv",
                                "dataType": "cr:Int64",
                                "source": {
                                    "@id": "rs-1/id/source",
                                    "fileObject": {"@id": "file-1"},
                                    "extract": {"column": "id"},
                                },
                            }
                        ],
                    }
                ],
            }
        ],
    }


def test_finish_registration_marks_valid_record_and_persists_metadata(
    tmp_path: Path,
) -> None:
    """Process a stored registration into a valid persisted adapter record."""
    database_path = tmp_path / "registry.sqlite3"
    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    (repository / "croissant.jsonld").write_text(
        json.dumps(_valid_adapter_document()),
        encoding="utf-8",
    )
    store = SQLiteRegistrationStore(database_path)
    submitted = submit_registration(
        adapter_name="Example Adapter",
        repository_location=str(repository),
        store=store,
    )

    processed = finish_registration(submitted.registration_id, store)

    assert processed.status == RegistrationStatus.VALID
    assert processed.metadata is not None
    assert processed.metadata["name"] == "Example Adapter"
    assert processed.metadata_path == str(repository / "croissant.jsonld")
    assert processed.profile_version == "v1"
    assert processed.uniqueness_key == "example-adapter::1.0.0"
    assert processed.updated_at is not None


def test_finish_registration_rejects_missing_registration(tmp_path: Path) -> None:
    """Fail when the requested registration identifier does not exist."""
    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")

    with pytest.raises(ValueError, match="Registration not found"):
        finish_registration("missing-registration", store)


def test_finish_registration_persists_invalid_status_and_errors(
    tmp_path: Path,
) -> None:
    """Persist validation errors when finishing an invalid registration."""
    database_path = tmp_path / "registry.sqlite3"
    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    invalid_document = _valid_adapter_document()
    invalid_document.pop("version")
    (repository / "croissant.jsonld").write_text(
        json.dumps(invalid_document),
        encoding="utf-8",
    )
    store = SQLiteRegistrationStore(database_path)
    submitted = submit_registration(
        adapter_name="Example Adapter",
        repository_location=str(repository),
        store=store,
    )

    processed = finish_registration(submitted.registration_id, store)

    assert processed.status == RegistrationStatus.INVALID
    assert processed.validation_errors
    assert processed.profile_version == "v1"
    assert any("version" in error for error in processed.validation_errors)


def test_finish_registration_records_unchanged_event_for_repeat_processing(
    tmp_path: Path,
) -> None:
    """Record UNCHANGED when a valid source is processed again without metadata changes."""
    database_path = tmp_path / "registry.sqlite3"
    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    (repository / "croissant.jsonld").write_text(
        json.dumps(_valid_adapter_document()),
        encoding="utf-8",
    )
    store = SQLiteRegistrationStore(database_path)
    submitted = submit_registration(
        adapter_name="Example Adapter",
        repository_location=str(repository),
        store=store,
    )

    first = finish_registration(submitted.registration_id, store)
    second = finish_registration(submitted.registration_id, store)

    assert first.status == RegistrationStatus.VALID
    assert second.status == RegistrationStatus.VALID

    import sqlite3

    with sqlite3.connect(database_path) as connection:
        entry_count = connection.execute(
            "SELECT COUNT(*) FROM registry_entries"
        ).fetchone()
        unchanged_events = connection.execute(
            """
            SELECT COUNT(*)
            FROM registration_events
            WHERE source_id = ? AND event_type = 'UNCHANGED'
            """,
            (submitted.registration_id,),
        ).fetchone()

    assert entry_count == (1,)
    assert unchanged_events == (1,)


def test_finish_registration_rejects_same_version_changed_file_and_records_event(
    tmp_path: Path,
) -> None:
    """Reject changed metadata for the same adapter_id and version and record the event."""
    database_path = tmp_path / "registry.sqlite3"
    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    original_document = _valid_adapter_document()
    metadata_path = repository / "croissant.jsonld"
    metadata_path.write_text(
        json.dumps(original_document),
        encoding="utf-8",
    )
    store = SQLiteRegistrationStore(database_path)
    submitted = submit_registration(
        adapter_name="Example Adapter",
        repository_location=str(repository),
        store=store,
    )

    finish_registration(submitted.registration_id, store)

    changed_document = _valid_adapter_document()
    changed_document["description"] = "Changed adapter description"
    metadata_path.write_text(
        json.dumps(changed_document),
        encoding="utf-8",
    )

    with pytest.raises(DuplicateRegistrationError, match="Please bump the version"):
        finish_registration(submitted.registration_id, store)

    import sqlite3

    with sqlite3.connect(database_path) as connection:
        rejected_events = connection.execute(
            """
            SELECT COUNT(*)
            FROM registration_events
            WHERE source_id = ? AND event_type = 'REJECTED_SAME_VERSION_CHANGED'
            """,
            (submitted.registration_id,),
        ).fetchone()
        entry_count = connection.execute(
            "SELECT COUNT(*) FROM registry_entries"
        ).fetchone()

    assert rejected_events == (1,)
    assert entry_count == (1,)


def test_refresh_active_registrations_processes_mixed_outcomes(
    tmp_path: Path,
) -> None:
    """Process all active sources and keep going across mixed outcomes."""
    database_path = tmp_path / "registry.sqlite3"
    store = SQLiteRegistrationStore(database_path)

    unchanged_repo = tmp_path / "unchanged-repo"
    unchanged_repo.mkdir()
    (unchanged_repo / "croissant.jsonld").write_text(
        json.dumps(
            _valid_adapter_document()
            | {"@id": "unchanged-adapter", "name": "Unchanged Adapter", "version": "1.0.0"}
        ),
        encoding="utf-8",
    )
    unchanged = submit_registration("Unchanged Adapter", str(unchanged_repo), store)
    finish_registration(unchanged.registration_id, store)

    valid_repo = tmp_path / "valid-repo"
    valid_repo.mkdir()
    (valid_repo / "croissant.jsonld").write_text(
        json.dumps(
            _valid_adapter_document()
            | {"@id": "new-valid-adapter", "name": "New Valid Adapter", "version": "2.0.0"}
        ),
        encoding="utf-8",
    )
    submit_registration("New Valid Adapter", str(valid_repo), store)

    invalid_repo = tmp_path / "invalid-repo"
    invalid_repo.mkdir()
    invalid_document = _valid_adapter_document() | {
        "@id": "invalid-adapter",
        "name": "Invalid Adapter",
    }
    invalid_document.pop("version")
    (invalid_repo / "croissant.jsonld").write_text(
        json.dumps(invalid_document),
        encoding="utf-8",
    )
    submit_registration("Invalid Adapter", str(invalid_repo), store)

    missing_repo = tmp_path / "missing-repo"
    missing_repo.mkdir()
    (missing_repo / "croissant.jsonld").write_text(
        json.dumps(
            _valid_adapter_document()
            | {"@id": "missing-adapter", "name": "Missing Adapter", "version": "3.0.0"}
        ),
        encoding="utf-8",
    )
    missing = submit_registration("Missing Adapter", str(missing_repo), store)
    (missing_repo / "croissant.jsonld").unlink()

    summary = refresh_active_registrations(store)

    assert summary.active_sources == 4
    assert summary.processed == 4
    assert summary.valid_created == 1
    assert summary.unchanged == 1
    assert summary.invalid == 1
    assert summary.fetch_failed == 1
    assert summary.duplicate == 0
    assert summary.rejected_same_version_changed == 0
    latest_refresh = store.get_latest_batch_refresh()
    assert latest_refresh is not None
    assert latest_refresh.active_sources == 4
    assert latest_refresh.processed == 4
    assert latest_refresh.fetch_failed == 1

    import sqlite3

    with sqlite3.connect(database_path) as connection:
        fetch_failed_events = connection.execute(
            """
            SELECT COUNT(*)
            FROM registration_events
            WHERE source_id = ? AND event_type = 'FETCH_FAILED'
            """,
            (missing.registration_id,),
        ).fetchone()

    assert fetch_failed_events == (1,)


def test_refresh_active_registrations_counts_duplicate_outcomes(
    tmp_path: Path,
) -> None:
    """Count duplicate outcomes without stopping the batch run."""
    database_path = tmp_path / "registry.sqlite3"
    store = SQLiteRegistrationStore(database_path)

    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()
    metadata = _valid_adapter_document() | {
        "@id": "duplicate-adapter",
        "name": "Duplicate Adapter",
        "version": "1.0.0",
    }
    (repo_a / "croissant.jsonld").write_text(json.dumps(metadata), encoding="utf-8")
    (repo_b / "croissant.jsonld").write_text(json.dumps(metadata), encoding="utf-8")

    first = submit_registration("Duplicate Adapter", str(repo_a), store)
    second = submit_registration("Duplicate Adapter Copy", str(repo_b), store)
    finish_registration(first.registration_id, store)

    summary = refresh_active_registrations(store)

    assert summary.active_sources == 2
    assert summary.processed == 2
    assert summary.unchanged == 1
    assert summary.duplicate == 1
    assert summary.fetch_failed == 0
    assert summary.invalid == 0


def test_revalidate_registration_reprocesses_corrected_invalid_source(
    tmp_path: Path,
) -> None:
    """Revalidate one previously invalid source immediately after metadata correction."""
    database_path = tmp_path / "registry.sqlite3"
    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    invalid_document = _valid_adapter_document()
    invalid_document.pop("version")
    metadata_path = repository / "croissant.jsonld"
    metadata_path.write_text(json.dumps(invalid_document), encoding="utf-8")

    store = SQLiteRegistrationStore(database_path)
    submitted = submit_registration(
        adapter_name="Example Adapter",
        repository_location=str(repository),
        store=store,
    )
    finish_registration(submitted.registration_id, store)

    metadata_path.write_text(json.dumps(_valid_adapter_document()), encoding="utf-8")

    revalidated = revalidate_registration(submitted.registration_id, store)

    assert revalidated.status == RegistrationStatus.VALID
    assert revalidated.metadata is not None
    assert revalidated.uniqueness_key == "example-adapter::1.0.0"

    import sqlite3

    with sqlite3.connect(database_path) as connection:
        revalidated_events = connection.execute(
            """
            SELECT COUNT(*)
            FROM registration_events
            WHERE source_id = ? AND event_type = 'REVALIDATED'
            """,
            (submitted.registration_id,),
        ).fetchone()
        valid_created_events = connection.execute(
            """
            SELECT COUNT(*)
            FROM registration_events
            WHERE source_id = ? AND event_type = 'VALID_CREATED'
            """,
            (submitted.registration_id,),
        ).fetchone()

    assert revalidated_events == (1,)
    assert valid_created_events == (1,)


def test_revalidate_registration_rejects_non_invalid_source(
    tmp_path: Path,
) -> None:
    """Reject revalidation when the source is not currently invalid or fetch-failed."""
    database_path = tmp_path / "registry.sqlite3"
    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    (repository / "croissant.jsonld").write_text(
        json.dumps(_valid_adapter_document()),
        encoding="utf-8",
    )
    store = SQLiteRegistrationStore(database_path)
    submitted = submit_registration(
        adapter_name="Example Adapter",
        repository_location=str(repository),
        store=store,
    )
    finish_registration(submitted.registration_id, store)

    with pytest.raises(ValueError, match="On-demand revalidation"):
        revalidate_registration(submitted.registration_id, store)
