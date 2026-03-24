from __future__ import annotations

import json
from pathlib import Path

from src.core.web.forms import (
    build_normalized_adapter_input_from_web_form,
)


def test_build_normalized_adapter_input_from_web_form_preserves_modes(tmp_path: Path) -> None:
    normalized = build_normalized_adapter_input_from_web_form(
        {
            "output": "adapter.jsonld",
            "name": "Example Adapter",
            "description": "Adapter description",
            "version": "1.0.0",
            "license": "MIT",
            "code_repository": "https://example.org/repo",
            "validate": "true",
            "dataset_generator": "auto",
            "creators_data": json.dumps(
                [{"name": "Alice", "affiliation": "Example Lab", "identifier": "https://orcid.org/1"}]
            ),
            "keywords": "adapter,biocypher",
            "datasets_data": json.dumps(
                [
                    {
                        "name": "Existing",
                        "description": "Existing dataset",
                        "version": "",
                        "license": "",
                        "url": "",
                        "uiMode": "existing",
                        "uiExistingPath": "/tmp/dataset.jsonld",
                    },
                    {
                        "name": "Generated",
                        "description": "Generated dataset",
                        "version": "1.0.0",
                        "license": "MIT",
                        "url": "https://example.org/dataset",
                        "uiMode": "generate",
                        "uiInputPath": "data/in/sample_networks_omnipath.tsv",
                        "uiCreators": ["Saezlab,,https://www.saezlab.com/"],
                    },
                ]
            ),
        },
        output_dir=tmp_path,
    )

    assert normalized["dataset_generator"] == "auto"
    assert normalized["adapter"]["output"] == "adapter.jsonld"
    assert normalized["datasets"][0] == {"mode": "existing", "path": "/tmp/dataset.jsonld"}
    assert normalized["datasets"][1]["mode"] == "generate"
    assert normalized["datasets"][1]["input"] == "data/in/sample_networks_omnipath.tsv"


def test_build_normalized_adapter_input_from_web_form_writes_manual_dataset(tmp_path: Path) -> None:
    normalized = build_normalized_adapter_input_from_web_form(
        {
            "output": "adapter.jsonld",
            "name": "Example Adapter",
            "description": "Adapter description",
            "version": "1.0.0",
            "license": "MIT",
            "code_repository": "https://example.org/repo",
            "validate": "true",
            "dataset_generator": "auto",
            "creators_data": json.dumps([{"name": "Alice"}]),
            "keywords": "adapter,biocypher",
            "datasets_data": json.dumps(
                [
                    {
                        "name": "Manual",
                        "description": "Manual dataset",
                        "version": "1.0.0",
                        "license": "MIT",
                        "url": "https://example.org/dataset",
                    }
                ]
            ),
        },
        output_dir=tmp_path,
    )

    assert normalized["datasets"][0]["mode"] == "existing"
    assert Path(normalized["datasets"][0]["path"]).exists()


def test_build_normalized_adapter_input_from_web_form_preserves_field_descriptions_via_manual_dataset(tmp_path: Path) -> None:
    normalized = build_normalized_adapter_input_from_web_form(
        {
            "output": "adapter.jsonld",
            "name": "Example Adapter",
            "description": "Adapter description",
            "version": "1.0.0",
            "license": "MIT",
            "code_repository": "https://example.org/repo",
            "validate": "true",
            "dataset_generator": "auto",
            "creators_data": json.dumps([{"name": "Alice"}]),
            "keywords": "adapter,biocypher",
            "datasets_data": json.dumps(
                [
                    {
                        "name": "Generated with edits",
                        "description": "Generated dataset",
                        "version": "1.0.0",
                        "license": "MIT",
                        "url": "https://example.org/dataset",
                        "uiMode": "generate",
                        "uiInputPath": "data/in/sample_networks_omnipath.tsv",
                        "uiForceManualMetadata": True,
                        "uiFieldPreview": [
                            {
                                "name": "id",
                                "mappedType": "sc:Integer",
                                "detectedType": "sc:Integer",
                                "example": "1",
                                "description": "",
                            },
                            {
                                "name": "name",
                                "mappedType": "sc:Text",
                                "detectedType": "sc:Text",
                                "example": "Alice",
                                "description": "Entity label",
                            },
                        ],
                    }
                ]
            ),
        },
        output_dir=tmp_path,
    )

    assert normalized["datasets"][0]["mode"] == "existing"
    path = Path(normalized["datasets"][0]["path"])
    assert path.exists()
    document = json.loads(path.read_text(encoding="utf-8"))
    fields = document["recordSet"][0]["field"]
    assert fields[0]["description"] == ""
    assert fields[1]["description"] == "Entity label"


def test_build_normalized_adapter_input_from_web_form_keeps_organization_dataset_creator(tmp_path: Path) -> None:
    normalized = build_normalized_adapter_input_from_web_form(
        {
            "output": "adapter.jsonld",
            "name": "Example Adapter",
            "description": "Adapter description",
            "version": "1.0.0",
            "license": "MIT",
            "code_repository": "https://example.org/repo",
            "validate": "true",
            "dataset_generator": "auto",
            "creators_data": json.dumps([{"name": "Alice"}]),
            "keywords": "adapter,biocypher",
            "datasets_data": json.dumps(
                [
                    {
                        "name": "Generated with org creator",
                        "description": "Generated dataset",
                        "version": "1.0.0",
                        "license": "MIT",
                        "url": "https://example.org/dataset",
                        "uiMode": "generate",
                        "uiInputPath": "data/in/sample_networks_omnipath.tsv",
                        "uiCreators": [
                            {
                                "creator_type": "Organization",
                                "name": "Saezlab",
                                "affiliations": "",
                                "email": "",
                                "url": "https://www.saezlab.com/",
                            }
                        ],
                    }
                ]
            ),
        },
        output_dir=tmp_path,
    )

    assert normalized["datasets"][0]["mode"] == "existing"
    path = Path(normalized["datasets"][0]["path"])
    document = json.loads(path.read_text(encoding="utf-8"))
    creator = document["creator"]
    assert creator["@type"] == "sc:Organization"
    assert creator["name"] == "Saezlab"
