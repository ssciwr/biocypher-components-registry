from __future__ import annotations

import pytest

from src.core.adapter.config import (
    build_adapter_request_from_mapping,
)
from src.core.adapter.request import AdapterGenerationRequest


def test_adapter_generation_request_validates_by_default() -> None:
    request = AdapterGenerationRequest(
        output_path="adapter.jsonld",
        name="Example Adapter",
        description="Adapter description",
        version="1.0.0",
        license_value="MIT",
        code_repository="https://example.org/repo",
        dataset_paths=["/tmp/dataset.jsonld"],
    )

    assert request.validate is True


def test_build_adapter_request_from_mapping_supports_existing_and_generated() -> None:
    request = build_adapter_request_from_mapping(
        {
            "dataset_generator": "auto",
            "validate": False,
            "adapter": {
                "output": "adapter.jsonld",
                "name": "Example Adapter",
                "description": "Adapter description",
                "version": "1.0.0",
                "license": "MIT",
                "code_repository": "https://example.org/repo",
                "adapter_id": "example-adapter",
                "keywords": ["adapter", "biocypher"],
                "creators": [
                    {
                        "name": "Alice",
                        "affiliation": "Example Lab",
                        "identifier": "https://orcid.org/0000-0000-0000-0001",
                    }
                ],
            },
            "datasets": [
                {"mode": "existing", "path": "/tmp/dataset.jsonld"},
                {
                    "mode": "generate",
                    "input": "data/in/sample_networks_omnipath.tsv",
                    "name": "Networks",
                    "description": "Network interactions",
                    "license": "MIT",
                    "url": "https://omnipathdb.org/",
                    "dataset_version": "1.0.0",
                    "date_published": "2016-06-01",
                    "citation": "https://omnipathdb.org/",
                    "creators": ["Saezlab,,https://www.saezlab.com/"],
                },
            ],
        }
    )

    assert request.dataset_generator == "auto"
    assert request.validate is False
    assert request.dataset_paths == ["/tmp/dataset.jsonld"]
    assert len(request.generated_datasets) == 1
    assert request.generated_datasets[0].input_path == "data/in/sample_networks_omnipath.tsv"


def test_build_adapter_request_from_mapping_inherits_adapter_creators_for_generated_datasets() -> None:
    request = build_adapter_request_from_mapping(
        {
            "dataset_generator": "auto",
            "adapter": {
                "name": "Example Adapter",
                "description": "Adapter description",
                "version": "1.0.0",
                "license": "MIT",
                "code_repository": "https://example.org/repo",
                "keywords": ["adapter", "biocypher"],
                "creators": [{"name": "Alice", "identifier": "https://orcid.org/0000-0000-0000-0001"}],
            },
            "datasets": [
                {
                    "mode": "generate",
                    "input": "data/in/sample_networks_omnipath.tsv",
                    "name": "Networks",
                },
            ],
        }
    )

    assert request.creators == ["Person|Alice||||https://orcid.org/0000-0000-0000-0001"]
    assert request.generated_datasets[0].creators == ["Person|Alice||||https://orcid.org/0000-0000-0000-0001"]


def test_build_adapter_request_from_mapping_requires_dataset_mode() -> None:
    with pytest.raises(Exception):
        build_adapter_request_from_mapping(
            {
                "adapter": {
                    "name": "Example Adapter",
                    "description": "Adapter description",
                    "version": "1.0.0",
                    "license": "MIT",
                    "code_repository": "https://example.org/repo",
                    "keywords": ["adapter"],
                    "creators": [{"name": "Alice"}],
                },
                "datasets": [{"mode": "unknown"}],
            }
        )
