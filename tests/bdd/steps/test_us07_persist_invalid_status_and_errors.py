from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from src.core.registration.models import RegistrationStatus, StoredRegistration
from src.core.registration.service import finish_registration, submit_registration
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore


scenarios("../features/us07_persist_invalid_status_and_errors.feature")


@pytest.fixture
def invalid_registration_context(tmp_path: Path) -> dict[str, Any]:
    """Provide shared state for invalid registration processing scenarios."""
    return {
        "database_path": tmp_path / "registry.sqlite3",
        "repository_path": tmp_path / "adapter-repo",
    }


def _invalid_adapter_document() -> dict[str, Any]:
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
        "@id": "clinical-knowledge-adapter",
        "name": "Clinical Knowledge Adapter",
        "description": "Adapter description",
        "conformsTo": "https://bioschemas.org/profiles/ComputationalTool/1.0-RELEASE/",
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


@given("a submitted registration points to invalid adapter metadata")
def submitted_registration_points_to_invalid_metadata(
    invalid_registration_context: dict[str, Any],
) -> None:
    """Store a submitted registration whose repository contains invalid metadata."""
    repository = invalid_registration_context["repository_path"]
    repository.mkdir()
    (repository / "croissant.jsonld").write_text(
        json.dumps(_invalid_adapter_document()),
        encoding="utf-8",
    )

    store = SQLiteRegistrationStore(invalid_registration_context["database_path"])
    registration = submit_registration(
        adapter_name="Clinical Knowledge Adapter",
        repository_location=str(repository),
        store=store,
    )
    invalid_registration_context["registration_id"] = registration.registration_id


@when("invalid registration processing finishes")
def invalid_registration_processing_finishes(
    invalid_registration_context: dict[str, Any],
) -> None:
    """Process the stored invalid registration through discovery and validation."""
    store = SQLiteRegistrationStore(invalid_registration_context["database_path"])
    invalid_registration_context["processed_registration"] = finish_registration(
        registration_id=invalid_registration_context["registration_id"],
        store=store,
    )


@then("the adapter status is INVALID")
def adapter_status_is_invalid(invalid_registration_context: dict[str, Any]) -> None:
    """Assert that the processed registration is marked as invalid."""
    processed_registration = invalid_registration_context["processed_registration"]

    assert isinstance(processed_registration, StoredRegistration)
    assert processed_registration.status == RegistrationStatus.INVALID


@then("detailed validation errors are persisted and retrievable")
def validation_errors_are_persisted(
    invalid_registration_context: dict[str, Any],
) -> None:
    """Assert that validation errors are stored and can be retrieved later."""
    processed_registration = invalid_registration_context["processed_registration"]
    store = SQLiteRegistrationStore(invalid_registration_context["database_path"])
    loaded = store.get_registration(processed_registration.registration_id)

    assert loaded is not None
    assert loaded.validation_errors
    assert any("version" in error for error in loaded.validation_errors)
