from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from src.core.adapter.config import build_adapter_request_from_mapping
from src.core.adapter.service import execute_request as execute_adapter_request
from src.core.shared.constants import METADATA_FILENAME
from src.core.validation import validate_adapter, validate_embedded_dataset


scenarios("../features/us02_guided_metadata.feature")


@pytest.fixture
def work_dir(tmp_path: Path) -> Path:
    return tmp_path / "guided_flow"


@pytest.fixture
def guidance_context() -> dict[str, Any]:
    return {}


def _valid_dataset_document() -> dict[str, Any]:
    return {
        "@context": {
            "@language": "en",
            "@vocab": "https://schema.org/",
            "citeAs": "cr:citeAs",
            "column": "cr:column",
            "conformsTo": "dct:conformsTo",
            "cr": "http://mlcommons.org/croissant/",
            "rai": "http://mlcommons.org/croissant/RAI/",
            "data": {"@id": "cr:data", "@type": "@json"},
            "dataType": {"@id": "cr:dataType", "@type": "@vocab"},
            "dct": "http://purl.org/dc/terms/",
            "examples": {"@id": "cr:examples", "@type": "@json"},
            "extract": "cr:extract",
            "field": "cr:field",
            "fileProperty": "cr:fileProperty",
            "fileObject": "cr:fileObject",
            "fileSet": "cr:fileSet",
            "format": "cr:format",
            "includes": "cr:includes",
            "isLiveDataset": "cr:isLiveDataset",
            "jsonPath": "cr:jsonPath",
            "key": "cr:key",
            "md5": "cr:md5",
            "parentField": "cr:parentField",
            "path": "cr:path",
            "recordSet": "cr:recordSet",
            "references": "cr:references",
            "regex": "cr:regex",
            "repeated": "cr:repeated",
            "replace": "cr:replace",
            "samplingRate": "cr:samplingRate",
            "sc": "https://schema.org/",
            "separator": "cr:separator",
            "source": "cr:source",
            "subField": "cr:subField",
            "transform": "cr:transform",
        },
        "@type": "sc:Dataset",
        "name": "Example dataset",
        "description": "Dataset description",
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


def _write_dataset_fixture(work_dir: Path) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)
    dataset_path = work_dir / "dataset.jsonld"
    dataset_path.write_text(json.dumps(_valid_dataset_document(), indent=2), encoding="utf-8")
    return dataset_path


@given("a maintainer provides mandatory metadata inputs")
def maintainer_inputs(guidance_context: dict[str, Any], work_dir: Path) -> None:
    dataset_path = _write_dataset_fixture(work_dir)
    guidance_context["inputs"] = {
        "adapter": {
            "name": "example-adapter",
            "description": "Example adapter metadata",
            "version": "0.1.0",
            "license": "MIT",
            "code_repository": "https://example.org/repo",
            "keywords": ["biology"],
            "creators": [{"name": "Ada Lovelace"}],
        },
        "datasets": [
            {
                "mode": "existing",
                "path": str(dataset_path),
            }
        ],
    }


@when("the guided metadata flow completes")
def guided_flow_completes(
    guidance_context: dict[str, Any],
    work_dir: Path,
) -> None:
    work_dir.mkdir(parents=True, exist_ok=True)
    inputs = guidance_context["inputs"]
    try:
        request = build_adapter_request_from_mapping(
            {
                **inputs,
                "validate": True,
            },
            output_override=str(work_dir / METADATA_FILENAME),
        )
        result = execute_adapter_request(request=request, generator="native")
        output_path = work_dir / METADATA_FILENAME
        metadata = json.loads(output_path.read_text(encoding="utf-8"))
        guidance_context["request"] = request
        guidance_context["result"] = result
        guidance_context["output_path"] = output_path
        guidance_context["metadata"] = metadata
        guidance_context["build_error"] = None
    except Exception as exc:  # noqa: BLE001
        guidance_context["build_error"] = exc


@then("a croissant.jsonld file is generated")
def croissant_file_generated(guidance_context: dict[str, Any], work_dir: Path) -> None:
    assert guidance_context.get("build_error") is None
    output_path = guidance_context["output_path"]
    assert isinstance(output_path, Path)
    assert output_path.name == METADATA_FILENAME
    assert output_path.exists()
    assert output_path.parent == work_dir


@then("the generated file contains the provided mandatory fields")
def generated_file_contains_inputs(guidance_context: dict[str, Any]) -> None:
    assert guidance_context.get("build_error") is None
    metadata = guidance_context["metadata"]
    inputs = guidance_context["inputs"]["adapter"]
    assert metadata["name"] == inputs["name"]
    assert metadata["description"] == inputs["description"]
    assert metadata["version"] == inputs["version"]
    assert metadata["license"] == "https://opensource.org/licenses/MIT"
    assert metadata["codeRepository"] == inputs["code_repository"]


@given("a croissant.jsonld generated by the guided flow")
def generated_by_guided_flow(
    guidance_context: dict[str, Any],
    work_dir: Path,
) -> None:
    maintainer_inputs(guidance_context, work_dir)
    guided_flow_completes(guidance_context, work_dir)


@when("the generated metadata is validated for mandatory fields")
def metadata_validated(guidance_context: dict[str, Any]) -> None:
    build_error = guidance_context.get("build_error")
    if build_error is not None:
        guidance_context["validation_result"] = build_error
        return
    metadata = guidance_context["metadata"]
    adapter_result = validate_adapter(metadata)
    embedded_results = [
        validate_embedded_dataset(dataset)
        for dataset in metadata.get("hasPart", [])
        if isinstance(dataset, dict)
    ]
    guidance_context["validation_result"] = (adapter_result, embedded_results)


@then("it passes the mandatory-field validation")
def passes_validation(guidance_context: dict[str, Any]) -> None:
    assert guidance_context.get("build_error") is None
    adapter_result, embedded_results = guidance_context["validation_result"]
    assert adapter_result.is_valid
    assert not adapter_result.errors
    assert all(result.is_valid for result in embedded_results)
    assert not [error for result in embedded_results for error in result.errors]


@given("mandatory inputs missing a required field")
def mandatory_inputs_missing_field(guidance_context: dict[str, Any], work_dir: Path) -> None:
    dataset_path = _write_dataset_fixture(work_dir)
    guidance_context["inputs"] = {
        "adapter": {
            "name": "example-adapter",
            "description": "Example adapter metadata",
            "version": "0.1.0",
            "license": "MIT",
            "code_repository": "https://example.org/repo",
            "keywords": [],
            "creators": [{"name": "Ada Lovelace"}],
        },
        "datasets": [
            {
                "mode": "existing",
                "path": str(dataset_path),
            }
        ],
    }


@then("mandatory-field validation fails")
def mandatory_validation_fails(guidance_context: dict[str, Any]) -> None:
    result = guidance_context["validation_result"]
    if isinstance(result, Exception):
        assert str(result)
        return
    if isinstance(result, tuple):
        adapter_result, _embedded_results = result
        assert not adapter_result.is_valid
        assert adapter_result.errors
        return
    assert not result.is_valid
    assert result.errors
