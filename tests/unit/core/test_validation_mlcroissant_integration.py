from __future__ import annotations

import mlcroissant as mlc

from src.core.validation.adapter import validate_adapter
from src.core.validation.dataset import validate_dataset, validate_embedded_dataset
from src.core.validation.mlcroissant import (
    validate_with_mlcroissant,
    validate_with_mlcroissant_report,
)
from src.core.shared.constants import CROISSANT_1_0_CONTEXT


def test_shared_context_is_croissant_1_0_compatible() -> None:
    assert CROISSANT_1_0_CONTEXT["equivalentProperty"] == "cr:equivalentProperty"
    croissant_1_1_only_terms = {
        "annotation",
        "arrayShape",
        "containedIn",
        "isArray",
        "readLines",
        "unArchive",
        "value",
    }
    assert croissant_1_1_only_terms.isdisjoint(CROISSANT_1_0_CONTEXT)


def test_validate_dataset_uses_mlcroissant_rules() -> None:
    document = {"@type": "sc:Dataset"}

    result = validate_dataset(document)

    assert not result.is_valid
    assert any(
        "doesn't extend https://schema.org/Dataset" in err for err in result.errors
    )


def test_mlcroissant_warning_is_not_relabelled_as_an_error(monkeypatch) -> None:
    class DummyValidationError(mlc.ValidationError):
        pass

    def fail_dataset(_document):
        raise DummyValidationError(
            "Found the following 1 error(s) during the validation:\n"
            "  -  Exact validator error.\n"
            "Found the following 1 warning(s) during the validation:\n"
            "  -  Recommended citation is missing."
        )

    monkeypatch.setattr("src.core.validation.mlcroissant.mlc.Dataset", fail_dataset)

    errors = validate_with_mlcroissant({"@type": "sc:Dataset"})

    assert errors == ["Exact validator error."]


def test_mlcroissant_warnings_are_reported_without_failing_validation(
    monkeypatch,
) -> None:
    class DummyIssues:
        warnings = {"Recommended citation is missing."}

    class DummyContext:
        issues = DummyIssues()

    class DummyMetadata:
        ctx = DummyContext()

    class DummyDataset:
        metadata = DummyMetadata()

    monkeypatch.setattr(
        "src.core.validation.mlcroissant.mlc.Dataset", lambda _document: DummyDataset()
    )

    report = validate_with_mlcroissant_report(
        {"@context": CROISSANT_1_0_CONTEXT, "@type": "sc:Dataset"}
    )

    assert report.errors == []
    assert report.warnings == ["Recommended citation is missing."]


def test_validate_adapter_combines_mlcroissant_and_schema_checks(monkeypatch) -> None:
    adapter_document = {
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
        },
        "@type": "SoftwareSourceCode",
        "name": "Adapter",
        "description": "desc",
        "version": "1.0.0",
        "license": "MIT",
        "codeRepository": "https://example.org/repo",
        "programmingLanguage": "Python",
        "targetProduct": "BioCypher",
        "creator": [],
        "keywords": [],
        "hasPart": [],
    }

    class DummyValidationError(mlc.ValidationError):
        pass

    def fail_dataset(_document):
        raise DummyValidationError(
            "Found the following 1 error(s) during the validation:\n"
            "  -  mlcroissant adapter error"
        )

    monkeypatch.setattr("src.core.validation.mlcroissant.mlc.Dataset", fail_dataset)

    result = validate_adapter(adapter_document)

    assert not result.is_valid
    assert any("mlcroissant adapter error" in err for err in result.errors)
    assert len(result.errors) >= 2


def test_validate_embedded_dataset_wraps_dataset_fragment() -> None:
    document = {
        "@type": "sc:Dataset",
        "dct:conformsTo": "http://mlcommons.org/croissant/1.0",
        "name": "Example dataset",
        "description": "Example dataset",
        "version": "1.0.0",
        "license": "https://opensource.org/licenses/MIT",
        "url": "https://example.org/dataset",
        "datePublished": "2024-01-01T00:00:00",
        "citeAs": "https://example.org/dataset",
        "creator": [{"@type": "sc:Person", "name": "Example Creator"}],
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

    result = validate_embedded_dataset(document)

    assert result.is_valid
