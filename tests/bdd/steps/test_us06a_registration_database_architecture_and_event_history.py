from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.core.registration.errors import DuplicateRegistrationError
from src.core.registration.service import finish_registration, submit_registration
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore


scenarios("../features/us06a_registration_database_architecture_and_event_history.feature")


@pytest.fixture
def registration_architecture_context(tmp_path: Path) -> dict[str, Any]:
    """Provide shared state for registration architecture scenarios."""
    return {
        "database_path": tmp_path / "registry.sqlite3",
        "repo_a": tmp_path / "adapter-repo-a",
        "repo_b": tmp_path / "adapter-repo-b",
    }


def _valid_adapter_document(
    *,
    adapter_id: str = "example-adapter",
    name: str = "Example Adapter",
    version: str = "1.0.0",
    description: str = "Adapter description",
) -> dict[str, Any]:
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
        "@id": adapter_id,
        "name": name,
        "description": description,
        "conformsTo": "https://bioschemas.org/profiles/ComputationalTool/1.0-RELEASE/",
        "version": version,
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


def _write_metadata(repository: Path, metadata: dict[str, Any]) -> None:
    repository.mkdir(exist_ok=True)
    (repository / "croissant.jsonld").write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )


@given("a maintainer submits a repository source with valid adapter metadata")
def maintainer_submits_repository_source_with_valid_metadata(
    registration_architecture_context: dict[str, Any],
) -> None:
    """Store a submitted source that points at valid metadata."""
    repository = registration_architecture_context["repo_a"]
    _write_metadata(repository, _valid_adapter_document())

    store = SQLiteRegistrationStore(registration_architecture_context["database_path"])
    registration = submit_registration(
        adapter_name="Example Adapter",
        repository_location=str(repository),
        store=store,
    )
    registration_architecture_context["registration_id"] = registration.registration_id


@when("the submission is stored in the registry")
def submission_is_stored_in_the_registry() -> None:
    """The submission side effect already happened in the given step."""


@then("a source record exists in registration_sources")
def source_record_exists_in_registration_sources(
    registration_architecture_context: dict[str, Any],
) -> None:
    """Assert that the submitted source is stored in the source table."""
    with sqlite3.connect(registration_architecture_context["database_path"]) as connection:
        row = connection.execute(
            """
            SELECT id, submitted_adapter_name, source_kind
            FROM registration_sources
            WHERE id = ?
            """,
            (registration_architecture_context["registration_id"],),
        ).fetchone()

    assert row is not None
    assert row[0] == registration_architecture_context["registration_id"]
    assert row[1] == "Example Adapter"
    assert row[2] == "local"


@then("a SUBMITTED event exists in registration_events")
def submitted_event_exists_in_registration_events(
    registration_architecture_context: dict[str, Any],
) -> None:
    """Assert that source submission created the expected event."""
    with sqlite3.connect(registration_architecture_context["database_path"]) as connection:
        row = connection.execute(
            """
            SELECT source_id, event_type
            FROM registration_events
            WHERE source_id = ? AND event_type = 'SUBMITTED'
            """,
            (registration_architecture_context["registration_id"],),
        ).fetchone()

    assert row == (
        registration_architecture_context["registration_id"],
        "SUBMITTED",
    )


@given("a stored registration source points to valid adapter metadata")
def stored_registration_source_points_to_valid_adapter_metadata(
    registration_architecture_context: dict[str, Any],
) -> None:
    """Create one submitted registration whose repository is valid."""
    maintainer_submits_repository_source_with_valid_metadata(
        registration_architecture_context
    )


@when("architecture registration processing finishes")
def architecture_registration_processing_finishes(
    registration_architecture_context: dict[str, Any],
) -> None:
    """Finish processing the stored registration."""
    store = SQLiteRegistrationStore(registration_architecture_context["database_path"])
    registration_architecture_context["processed_registration"] = finish_registration(
        registration_architecture_context["registration_id"],
        store,
    )


@then("a canonical valid record exists in registry_entries")
def canonical_valid_record_exists_in_registry_entries(
    registration_architecture_context: dict[str, Any],
) -> None:
    """Assert that valid processing created a canonical registry entry."""
    with sqlite3.connect(registration_architecture_context["database_path"]) as connection:
        row = connection.execute(
            """
            SELECT source_id, adapter_name, adapter_version, uniqueness_key
            FROM registry_entries
            WHERE source_id = ?
            """,
            (registration_architecture_context["registration_id"],),
        ).fetchone()

    assert row == (
        registration_architecture_context["registration_id"],
        "Example Adapter",
        "1.0.0",
        "example-adapter::1.0.0",
    )


@then("a VALID_CREATED event exists in registration_events")
def valid_created_event_exists_in_registration_events(
    registration_architecture_context: dict[str, Any],
) -> None:
    """Assert that valid processing recorded the canonical-entry event."""
    with sqlite3.connect(registration_architecture_context["database_path"]) as connection:
        row = connection.execute(
            """
            SELECT source_id, event_type
            FROM registration_events
            WHERE source_id = ? AND event_type = 'VALID_CREATED'
            """,
            (registration_architecture_context["registration_id"],),
        ).fetchone()

    assert row == (
        registration_architecture_context["registration_id"],
        "VALID_CREATED",
    )


@given("a valid source has already been processed once")
def valid_source_has_already_been_processed_once(
    registration_architecture_context: dict[str, Any],
) -> None:
    """Create one canonical entry so unchanged reprocessing can be exercised."""
    stored_registration_source_points_to_valid_adapter_metadata(
        registration_architecture_context
    )
    architecture_registration_processing_finishes(registration_architecture_context)


@when("architecture registration processing finishes again without metadata changes")
def architecture_registration_processing_finishes_again_without_metadata_changes(
    registration_architecture_context: dict[str, Any],
) -> None:
    """Process the same source a second time without editing metadata."""
    store = SQLiteRegistrationStore(registration_architecture_context["database_path"])
    registration_architecture_context["repeat_result"] = finish_registration(
        registration_architecture_context["registration_id"],
        store,
    )


@then("the canonical registry state remains correct for unchanged processing")
def canonical_registry_state_remains_correct_for_unchanged_processing(
    registration_architecture_context: dict[str, Any],
) -> None:
    """Assert that unchanged processing does not create another canonical entry."""
    with sqlite3.connect(registration_architecture_context["database_path"]) as connection:
        entry_count = connection.execute(
            "SELECT COUNT(*) FROM registry_entries"
        ).fetchone()

    assert entry_count == (1,)


@given("a canonical valid entry already exists for an adapter_id and version")
def canonical_valid_entry_already_exists_for_adapter_id_and_version(
    registration_architecture_context: dict[str, Any],
) -> None:
    """Create the first canonical valid entry that the duplicate will collide with."""
    valid_source_has_already_been_processed_once(registration_architecture_context)


@when("another source is processed with the same canonical metadata")
def another_source_is_processed_with_the_same_canonical_metadata(
    registration_architecture_context: dict[str, Any],
) -> None:
    """Submit and process another source that declares the same metadata identity."""
    repository = registration_architecture_context["repo_b"]
    _write_metadata(repository, _valid_adapter_document())
    store = SQLiteRegistrationStore(registration_architecture_context["database_path"])
    duplicate = submit_registration(
        adapter_name="Example Adapter Duplicate",
        repository_location=str(repository),
        store=store,
    )
    registration_architecture_context["duplicate_registration_id"] = (
        duplicate.registration_id
    )
    try:
        finish_registration(duplicate.registration_id, store)
    except DuplicateRegistrationError as exc:
        registration_architecture_context["duplicate_error"] = exc
    else:
        registration_architecture_context["duplicate_error"] = None


@then("the canonical registry state remains correct for duplicate processing")
def canonical_registry_state_remains_correct_for_duplicate_processing(
    registration_architecture_context: dict[str, Any],
) -> None:
    """Assert that duplicate processing preserves the original canonical entry."""
    assert registration_architecture_context["duplicate_error"] is not None
    with sqlite3.connect(registration_architecture_context["database_path"]) as connection:
        entry_count = connection.execute(
            "SELECT COUNT(*) FROM registry_entries"
        ).fetchone()

    assert entry_count == (1,)


@given("a stored registration source points to invalid adapter metadata")
def stored_registration_source_points_to_invalid_adapter_metadata(
    registration_architecture_context: dict[str, Any],
) -> None:
    """Submit a source whose metadata is missing the top-level adapter version."""
    repository = registration_architecture_context["repo_a"]
    metadata = _valid_adapter_document()
    metadata.pop("version", None)
    _write_metadata(repository, metadata)

    store = SQLiteRegistrationStore(registration_architecture_context["database_path"])
    registration = submit_registration(
        adapter_name="Broken Adapter",
        repository_location=str(repository),
        store=store,
    )
    registration_architecture_context["registration_id"] = registration.registration_id


@when("architecture registration processing finishes for invalid metadata")
def architecture_registration_processing_finishes_for_invalid_metadata(
    registration_architecture_context: dict[str, Any],
) -> None:
    """Process the invalid source and persist the failed validation result."""
    store = SQLiteRegistrationStore(registration_architecture_context["database_path"])
    registration_architecture_context["invalid_result"] = finish_registration(
        registration_architecture_context["registration_id"],
        store,
    )


@then("the canonical registry state remains correct for invalid processing")
def canonical_registry_state_remains_correct_for_invalid_processing(
    registration_architecture_context: dict[str, Any],
) -> None:
    """Assert that invalid processing does not create canonical registry entries."""
    with sqlite3.connect(registration_architecture_context["database_path"]) as connection:
        entry_count = connection.execute(
            "SELECT COUNT(*) FROM registry_entries"
        ).fetchone()

    assert entry_count == (0,)


@then(parsers.parse("the outcome is recorded in registration_events as {event_type}"))
def outcome_is_recorded_in_registration_events_as(
    registration_architecture_context: dict[str, Any],
    event_type: str,
) -> None:
    """Assert that the expected event type is written for the active registration."""
    registration_id = registration_architecture_context.get(
        "duplicate_registration_id",
        registration_architecture_context.get("registration_id"),
    )
    if event_type == "UNCHANGED":
        registration_id = registration_architecture_context["registration_id"]
    with sqlite3.connect(registration_architecture_context["database_path"]) as connection:
        row = connection.execute(
            """
            SELECT source_id, event_type
            FROM registration_events
            WHERE source_id = ? AND event_type = ?
            """,
            (registration_id, event_type),
        ).fetchone()

    assert row == (registration_id, event_type)
