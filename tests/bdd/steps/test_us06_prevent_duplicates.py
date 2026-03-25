from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from src.core.registration.errors import DuplicateRegistrationError
from src.core.registration.service import finish_registration, submit_registration
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore


scenarios("../features/us06_prevent_duplicates.feature")


@pytest.fixture
def duplicate_context(tmp_path: Path) -> dict[str, Any]:
    """Provide shared state for duplicate-registration scenarios."""
    return {
        "database_path": tmp_path / "registry.sqlite3",
        "repo_a": tmp_path / "adapter-repo-a",
        "repo_b": tmp_path / "adapter-repo-b",
    }


def _valid_adapter_document(
    name: str = "Example Adapter",
    version: str = "1.0.0",
    adapter_id: str = "example-adapter",
) -> dict:
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


@given("an adapter is already stored with a uniqueness key")
def adapter_already_stored_with_uniqueness_key(
    duplicate_context: dict[str, Any],
) -> None:
    """Store and finish one valid registration to occupy the uniqueness key."""
    repo_a = duplicate_context["repo_a"]
    repo_a.mkdir()
    (repo_a / "croissant.jsonld").write_text(
        json.dumps(
            _valid_adapter_document(
                name="OmniPath Adapter",
                adapter_id="omnipath-adapter",
            )
        ),
        encoding="utf-8",
    )

    store = SQLiteRegistrationStore(duplicate_context["database_path"])
    registration = submit_registration(
        adapter_name="OmniPath Adapter",
        repository_location=str(repo_a),
        store=store,
    )
    finish_registration(registration.registration_id, store)


@when("another registration uses the same uniqueness key")
def another_registration_uses_same_uniqueness_key(
    duplicate_context: dict[str, Any],
) -> None:
    """Attempt to finish a second valid registration with the same uniqueness key."""
    repo_b = duplicate_context["repo_b"]
    repo_b.mkdir()
    (repo_b / "croissant.jsonld").write_text(
        json.dumps(
            _valid_adapter_document(
                name="omnipath adapter",
                adapter_id="omnipath-adapter",
            )
        ),
        encoding="utf-8",
    )

    store = SQLiteRegistrationStore(duplicate_context["database_path"])
    duplicate = submit_registration(
        adapter_name="omnipath adapter",
        repository_location=str(repo_b),
        store=store,
    )
    try:
        finish_registration(duplicate.registration_id, store)
    except Exception as exc:  # noqa: BLE001
        duplicate_context["error"] = exc
    else:
        duplicate_context["error"] = None


@then("the system rejects the new submission as duplicate")
def system_rejects_duplicate_submission(duplicate_context: dict[str, Any]) -> None:
    """Assert that duplicate completion is rejected."""
    error = duplicate_context["error"]

    assert isinstance(error, DuplicateRegistrationError)
