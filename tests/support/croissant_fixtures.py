"""Shared Croissant document fixtures reused across test modules.

Extracted to avoid duplicating the same sample dataset document literal in
many test files (see SonarQube duplicated-lines findings).
"""

from __future__ import annotations

from copy import deepcopy

from src.core.shared.constants import STANDARD_CONTEXT

_ADAPTER_CONTEXT_TERMS = (
    "@language",
    "@vocab",
    "citeAs",
    "column",
    "conformsTo",
    "cr",
    "dataType",
    "dct",
    "examples",
    "extract",
    "field",
    "fileObject",
    "recordSet",
    "sc",
    "source",
)


def sample_dataset_document() -> dict:
    """Return a minimal valid Croissant dataset document for test fixtures."""
    return {
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


def sample_adapter_document() -> dict:
    return {
        "@context": deepcopy(
            {term: STANDARD_CONTEXT[term] for term in _ADAPTER_CONTEXT_TERMS}
        ),
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
        "hasPart": [sample_dataset_document()],
    }
