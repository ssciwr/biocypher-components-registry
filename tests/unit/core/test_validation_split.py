from __future__ import annotations

from copy import deepcopy

from src.core.shared.constants import STANDARD_CONTEXT
from src.core.validation.adapter import validate_adapter
from src.core.validation.dataset import validate_dataset


def _valid_dataset_document() -> dict:
    return {
        "@context": deepcopy(STANDARD_CONTEXT),
        "@type": "sc:Dataset",
        "name": "Example dataset",
        "description": "Example dataset",
        "conformsTo": "http://mlcommons.org/croissant/1.0",
        "citeAs": "https://example.org/dataset",
        "creator": {"@type": "sc:Person", "name": "Example Creator"},
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


def test_validate_dataset_accepts_dataset_root() -> None:
    document = _valid_dataset_document()

    result = validate_dataset(document)

    assert result.is_valid


def test_validate_adapter_rejects_dataset_root() -> None:
    document = _valid_dataset_document()

    result = validate_adapter(document)

    assert not result.is_valid


def test_validate_adapter_accepts_singleton_creator_and_has_part() -> None:
    dataset = _valid_dataset_document()
    dataset.pop("@context")
    document = {
        "@context": deepcopy(STANDARD_CONTEXT),
        "@type": "SoftwareSourceCode",
        "name": "BioCypher CollecTRI Adapter",
        "description": "Adapter integrating the CollecTRI resource into BioCypher.",
        "version": "0.0.1",
        "license": "https://github.com/biocypher/collectri/blob/main/LICENSE",
        "codeRepository": "https://github.com/biocypher/collectri",
        "creator": {"@type": "Person", "name": "Sebastian Lobentanzer"},
        "keywords": ["gene regulatory network"],
        "hasPart": dataset,
    }

    result = validate_adapter(document)

    assert result.is_valid
    assert result.errors == []
    assert isinstance(document["creator"], dict)
