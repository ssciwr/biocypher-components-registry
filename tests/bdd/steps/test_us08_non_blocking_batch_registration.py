from __future__ import annotations

import io
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from src.core.registration.service import (
    finish_registration,
    refresh_active_registrations,
    submit_registration,
)
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore
from src.core.web import server as web_ui_new


scenarios("../features/us08_non_blocking_batch_registration.feature")


@pytest.fixture
def batch_registration_context(tmp_path: Path) -> dict[str, Any]:
    """Provide shared state for non-blocking batch registration scenarios."""
    return {
        "database_path": tmp_path / "registry.sqlite3",
        "repo_a": tmp_path / "adapter-repo-a",
        "repo_b": tmp_path / "adapter-repo-b",
        "repo_c": tmp_path / "adapter-repo-c",
    }


def _valid_adapter_document(
    *,
    adapter_id: str = "example-adapter",
    name: str = "Example Adapter",
    version: str = "1.0.0",
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
        "description": "Adapter description",
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


@given("active sources include valid and invalid adapters")
def active_sources_include_valid_and_invalid_adapters(
    batch_registration_context: dict[str, Any],
) -> None:
    """Create one valid and one invalid active source before the batch run."""
    valid_repo = batch_registration_context["repo_a"]
    invalid_repo = batch_registration_context["repo_b"]
    _write_metadata(
        valid_repo,
        _valid_adapter_document(
            adapter_id="batch-valid-adapter",
            name="Batch Valid Adapter",
            version="1.0.0",
        ),
    )
    invalid_document = _valid_adapter_document(
        adapter_id="batch-invalid-adapter",
        name="Batch Invalid Adapter",
        version="1.0.0",
    )
    invalid_document.pop("version")
    _write_metadata(invalid_repo, invalid_document)

    store = SQLiteRegistrationStore(batch_registration_context["database_path"])
    submit_registration("Batch Valid Adapter", str(valid_repo), store)
    submit_registration("Batch Invalid Adapter", str(invalid_repo), store)


@given("one active source cannot be fetched and another is valid")
def one_active_source_cannot_be_fetched_and_another_is_valid(
    batch_registration_context: dict[str, Any],
) -> None:
    """Create one valid source and one source that will fail discovery in the batch."""
    valid_repo = batch_registration_context["repo_a"]
    missing_repo = batch_registration_context["repo_b"]
    _write_metadata(
        valid_repo,
        _valid_adapter_document(
            adapter_id="fetch-valid-adapter",
            name="Fetch Valid Adapter",
            version="1.0.0",
        ),
    )
    _write_metadata(
        missing_repo,
        _valid_adapter_document(
            adapter_id="missing-adapter",
            name="Missing Adapter",
            version="1.0.0",
        ),
    )

    store = SQLiteRegistrationStore(batch_registration_context["database_path"])
    submit_registration("Fetch Valid Adapter", str(valid_repo), store)
    broken = submit_registration("Missing Adapter", str(missing_repo), store)
    batch_registration_context["broken_registration_id"] = broken.registration_id
    (missing_repo / "croissant.jsonld").unlink()


@given("an active source previously failed validation")
def an_active_source_previously_failed_validation(
    batch_registration_context: dict[str, Any],
) -> None:
    """Create one submitted source and process it once as invalid."""
    repository = batch_registration_context["repo_a"]
    invalid_document = _valid_adapter_document(
        adapter_id="corrected-adapter",
        name="Corrected Adapter",
        version="1.0.0",
    )
    invalid_document.pop("version")
    _write_metadata(repository, invalid_document)

    store = SQLiteRegistrationStore(batch_registration_context["database_path"])
    registration = submit_registration("Corrected Adapter", str(repository), store)
    batch_registration_context["corrected_registration_id"] = registration.registration_id
    finish_registration(registration.registration_id, store)


@given("the metadata is corrected before the next scheduled run")
def metadata_is_corrected_before_the_next_scheduled_run(
    batch_registration_context: dict[str, Any],
) -> None:
    """Rewrite the invalid metadata so the next batch run can accept it."""
    repository = batch_registration_context["repo_a"]
    _write_metadata(
        repository,
        _valid_adapter_document(
            adapter_id="corrected-adapter",
            name="Corrected Adapter",
            version="1.0.0",
        ),
    )


@when("the batch registration workflow runs")
def batch_registration_workflow_runs(
    batch_registration_context: dict[str, Any],
) -> None:
    """Run the non-blocking batch registration flow across active sources."""
    store = SQLiteRegistrationStore(batch_registration_context["database_path"])
    batch_registration_context["summary"] = refresh_active_registrations(store)


@when("the batch registration workflow is triggered from the web UI")
def batch_registration_workflow_is_triggered_from_the_web_ui(
    batch_registration_context: dict[str, Any],
) -> None:
    """Trigger the batch refresh from the lightweight web handler."""
    handler = web_ui_new._Handler
    handler.output_dir = batch_registration_context["database_path"].parent
    handler.last_output_path = batch_registration_context["database_path"].parent / "generated.jsonld"
    handler.registration_db_path = batch_registration_context["database_path"]

    post_handler = object.__new__(handler)
    post_handler.path = "/registry/refresh"
    post_handler.headers = {"Content-Length": "0"}
    post_handler.rfile = io.BytesIO(b"")
    captured: list[tuple[int, str]] = []
    post_handler._send = lambda content, status=200: captured.append((status, content))

    handler.do_POST(post_handler)
    batch_registration_context["web_response"] = captured


@then("remaining adapters are still processed")
def remaining_adapters_are_still_processed(
    batch_registration_context: dict[str, Any],
) -> None:
    """Assert that the batch summary reports all active sources as processed."""
    summary = batch_registration_context["summary"]

    assert summary.processed == summary.active_sources
    assert summary.processed > 0


@then("the run completes with mixed outcomes")
def run_completes_with_mixed_outcomes(
    batch_registration_context: dict[str, Any],
) -> None:
    """Assert that the batch saw both valid and invalid outcomes."""
    summary = batch_registration_context["summary"]

    assert summary.valid_created == 1
    assert summary.invalid == 1


@then("the run records a FETCH_FAILED outcome")
def run_records_a_fetch_failed_outcome(
    batch_registration_context: dict[str, Any],
) -> None:
    """Assert that the broken source records a fetch failure event."""
    summary = batch_registration_context["summary"]

    assert summary.fetch_failed == 1
    with sqlite3.connect(batch_registration_context["database_path"]) as connection:
        row = connection.execute(
            """
            SELECT source_id, event_type
            FROM registration_events
            WHERE source_id = ? AND event_type = 'FETCH_FAILED'
            """,
            (batch_registration_context["broken_registration_id"],),
        ).fetchone()

    assert row == (
        batch_registration_context["broken_registration_id"],
        "FETCH_FAILED",
    )


@then("the source is reprocessed immediately")
def source_is_reprocessed_immediately(
    batch_registration_context: dict[str, Any],
) -> None:
    """Assert that the corrected source is processed by the immediate batch run."""
    summary = batch_registration_context["summary"]

    assert summary.processed == 1
    assert summary.valid_created == 1


@then("the registry records a VALID_CREATED outcome for the corrected source")
def registry_records_valid_created_for_corrected_source(
    batch_registration_context: dict[str, Any],
) -> None:
    """Assert that the corrected source now produces a valid canonical entry."""
    with sqlite3.connect(batch_registration_context["database_path"]) as connection:
        row = connection.execute(
            """
            SELECT source_id, event_type
            FROM registration_events
            WHERE source_id = ? AND event_type = 'VALID_CREATED'
            ORDER BY finished_at DESC
            LIMIT 1
            """,
            (batch_registration_context["corrected_registration_id"],),
        ).fetchone()

    assert row == (
        batch_registration_context["corrected_registration_id"],
        "VALID_CREATED",
    )


@then("the UI shows the batch summary")
def ui_shows_the_batch_summary(
    batch_registration_context: dict[str, Any],
) -> None:
    """Assert that the web refresh page renders the batch summary."""
    response = batch_registration_context["web_response"]

    assert response
    assert response[0][0] == 200
    assert "Registry Operations" in response[0][1]
    assert "Latest Batch Summary" in response[0][1]
    assert "Batch refresh finished." in response[0][1]


@then("the latest per-source outcomes are visible")
def latest_per_source_outcomes_are_visible(
    batch_registration_context: dict[str, Any],
) -> None:
    """Assert that the web refresh page lists the latest source outcomes."""
    response = batch_registration_context["web_response"]

    assert "Batch Valid Adapter" in response[0][1]
    assert "Batch Invalid Adapter" in response[0][1]
    assert "VALID_CREATED" in response[0][1]
    assert "INVALID_SCHEMA" in response[0][1]
