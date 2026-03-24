from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from src.core.registration.models import RegistrationStatus
from src.core.registration.service import (
    finish_registration,
    revalidate_registration,
    submit_registration,
)
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore


scenarios("../features/us09_on_demand_revalidation.feature")


@pytest.fixture
def revalidation_context(tmp_path: Path) -> dict[str, Any]:
    """Provide shared state for on-demand revalidation scenarios."""
    return {
        "database_path": tmp_path / "registry.sqlite3",
        "repository_path": tmp_path / "adapter-repo",
    }


def _valid_adapter_document() -> dict[str, Any]:
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


@given("an adapter is currently marked INVALID")
def adapter_is_currently_marked_invalid(
    revalidation_context: dict[str, Any],
) -> None:
    """Create one invalid source and process it once as INVALID."""
    repository = revalidation_context["repository_path"]
    repository.mkdir()
    invalid_document = _valid_adapter_document()
    invalid_document.pop("version")
    (repository / "croissant.jsonld").write_text(
        json.dumps(invalid_document),
        encoding="utf-8",
    )

    store = SQLiteRegistrationStore(revalidation_context["database_path"])
    registration = submit_registration(
        adapter_name="Clinical Knowledge Adapter",
        repository_location=str(repository),
        store=store,
    )
    finish_registration(registration.registration_id, store)
    revalidation_context["registration_id"] = registration.registration_id


@given("the maintainer corrects the metadata")
def maintainer_corrects_the_metadata(
    revalidation_context: dict[str, Any],
) -> None:
    """Fix the invalid metadata before revalidation is triggered."""
    repository = revalidation_context["repository_path"]
    (repository / "croissant.jsonld").write_text(
        json.dumps(_valid_adapter_document()),
        encoding="utf-8",
    )


@when("on-demand revalidation is triggered")
def on_demand_revalidation_is_triggered(
    revalidation_context: dict[str, Any],
) -> None:
    """Reprocess the corrected invalid source immediately."""
    store = SQLiteRegistrationStore(revalidation_context["database_path"])
    revalidation_context["processed_registration"] = revalidate_registration(
        registration_id=revalidation_context["registration_id"],
        store=store,
    )


@then("the system reprocesses the adapter immediately")
def system_reprocesses_the_adapter_immediately(
    revalidation_context: dict[str, Any],
) -> None:
    """Assert that revalidation produced a processed registration result."""
    processed_registration = revalidation_context["processed_registration"]

    assert processed_registration.metadata is not None
    assert processed_registration.metadata["name"] == "Clinical Knowledge Adapter"


@then("the adapter status is updated to VALID")
def adapter_status_is_updated_to_valid(
    revalidation_context: dict[str, Any],
) -> None:
    """Assert that revalidation upgrades the source to VALID."""
    processed_registration = revalidation_context["processed_registration"]

    assert processed_registration.status == RegistrationStatus.VALID
