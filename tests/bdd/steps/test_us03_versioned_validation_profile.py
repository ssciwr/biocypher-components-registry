from __future__ import annotations

from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from src.core.schema.profile import ACTIVE_PROFILE_VERSION, load_active_schema
from src.core.validation.adapter import validate_adapter
from src.core.validation.results import ValidationResult


scenarios("../features/us03_versioned_validation_profile.feature")


@pytest.fixture
def validation_context() -> dict[str, Any]:
    return {}


def _valid_adapter_document() -> dict[str, Any]:
    return {
        "@context": {
            "@language": "en",
            "@vocab": "https://schema.org/",
            "sc": "https://schema.org/",
            "cr": "http://mlcommons.org/croissant/",
            "dct": "http://purl.org/dc/terms/",
            "conformsTo": "dct:conformsTo",
            "recordSet": "cr:recordSet",
            "field": "cr:field",
            "source": "cr:source",
            "fileObject": "cr:fileObject",
            "extract": "cr:extract",
            "column": "cr:column",
            "dataType": {"@id": "cr:dataType", "@type": "@vocab"},
            "examples": {"@id": "cr:examples", "@type": "@json"},
            "citeAs": "cr:citeAs",
        },
        "@type": "SoftwareSourceCode",
        "@id": "example-adapter",
        "name": "Example Adapter",
        "description": "Adapter description",
        "dct:conformsTo": "https://bioschemas.org/profiles/ComputationalTool/1.0-RELEASE/",
        "version": "1.0.0",
        "license": "https://opensource.org/licenses/MIT",
        "codeRepository": "https://example.org/repo",
        "programmingLanguage": "Python",
        "targetProduct": "BioCypher",
        "creator": [
            {
                "@type": "Person",
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
                "dct:conformsTo": "http://mlcommons.org/croissant/1.0",
                "citeAs": "https://example.org/dataset",
                "creator": [
                    {
                        "@type": "sc:Person",
                        "name": "Example Creator",
                    }
                ],
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


@given("valid adapter metadata for validation")
def valid_adapter_metadata_for_validation(
    monkeypatch: pytest.MonkeyPatch,
    validation_context: dict[str, Any],
) -> None:
    call_log: list[str] = []
    original_loader = load_active_schema

    def tracked_loader() -> dict[str, Any]:
        call_log.append(ACTIVE_PROFILE_VERSION)
        return original_loader()

    monkeypatch.setattr("src.core.validation.adapter.load_active_schema", tracked_loader)
    validation_context["metadata"] = _valid_adapter_document()
    validation_context["call_log"] = call_log


@when("adapter validation starts")
def adapter_validation_starts(validation_context: dict[str, Any]) -> None:
    metadata = validation_context["metadata"]
    validation_context["result"] = validate_adapter(metadata)


@then("exactly one active validation profile version is used")
def exactly_one_active_profile_used(validation_context: dict[str, Any]) -> None:
    result = validation_context["result"]
    call_log = validation_context["call_log"]

    assert isinstance(result, ValidationResult)
    assert result.profile_version == ACTIVE_PROFILE_VERSION
    assert call_log == [ACTIVE_PROFILE_VERSION]


@when("adapter validation completes")
def adapter_validation_completes(validation_context: dict[str, Any]) -> None:
    adapter_validation_starts(validation_context)


@then("the validation result records the active profile version")
def validation_result_records_profile_version(
    validation_context: dict[str, Any],
) -> None:
    result = validation_context["result"]

    assert isinstance(result, ValidationResult)
    assert isinstance(result.profile_version, str)
    assert result.profile_version == ACTIVE_PROFILE_VERSION
