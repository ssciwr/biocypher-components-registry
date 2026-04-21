from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.api.routers import metadata as metadata_router
from src.api.app import create_app
from src.api.schemas.metadata import (
    ADAPTER_METADATA_GENERATE_EXAMPLE,
    DATASET_METADATA_GENERATE_EXAMPLE,
    METADATA_VALIDATE_DATASET_EXAMPLE,
)
from src.core.adapter.document import build_adapter_creator, build_adapter_document
from src.core.dataset.request import GenerationResult


METADATA_VALIDATE_PATH = "/api/v1/metadata/validate"
DATASET_GENERATE_PATH = "/api/v1/metadata/datasets/generate"
ADAPTER_GENERATE_PATH = "/api/v1/metadata/adapters/generate"


# ===========================================================
# Metadata Validation Endpoint Tests
# ===========================================================


def _valid_dataset_document() -> dict[str, object]:
    """Return a valid dataset metadata document for validation tests."""
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


def _invalid_adapter_document() -> dict[str, object]:
    """Return invalid adapter metadata for validation tests."""
    return {
        "@context": {"@vocab": "https://schema.org/"},
        "@type": "SoftwareSourceCode",
        "@id": "example-adapter",
        "name": "Example Adapter",
    }


def _valid_adapter_document() -> dict[str, object]:
    """Return a valid adapter metadata document for generation tests."""
    embedded_dataset = dict(_valid_dataset_document())
    embedded_dataset.pop("@context", None)
    embedded_dataset["creator"] = [embedded_dataset["creator"]]
    return build_adapter_document(
        name="Example Adapter",
        description="Example adapter",
        version="1.0.0",
        license_value="https://opensource.org/licenses/MIT",
        code_repository="https://github.com/example/example-adapter",
        creators=[
            build_adapter_creator(
                name="Example Creator",
                affiliation="Example Lab",
                identifier="https://orcid.org/0000-0000-0000-0000",
            )
        ],
        keywords=["adapter", "biocypher"],
        datasets=[embedded_dataset],
        adapter_id="example-adapter",
    )


def _dataset_generate_payload(
    input_path: str,
    **overrides: object,
) -> dict[str, object]:
    """Build a minimal dataset generation request body for API tests."""
    payload: dict[str, object] = {"input_path": input_path}
    payload.update(overrides)
    return payload


def _adapter_generate_payload(**overrides: object) -> dict[str, object]:
    """Build a valid minimal adapter generation request body for API tests."""
    payload: dict[str, object] = {
        "name": "Example Adapter",
        "description": "Example adapter",
        "version": "1.0.0",
        "license": "https://opensource.org/licenses/MIT",
        "code_repository": "https://github.com/example/example-adapter",
        "creators": ["Example Creator"],
        "keywords": ["adapter"],
    }
    payload.update(overrides)
    return payload


def test_validate_metadata_endpoint_auto_detects_dataset() -> None:
    """Validate dataset metadata with automatic type detection."""
    client = TestClient(create_app())

    response = client.post(
        METADATA_VALIDATE_PATH,
        json={"metadata": _valid_dataset_document()},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["kind"] == "dataset"
    assert payload["is_valid"] is True
    assert payload["profile_version"] == "v1"
    assert payload["errors"] == []
    assert payload["checks"][0]["name"] == "Croissant compliance"


def test_validate_metadata_endpoint_returns_invalid_adapter_result() -> None:
    """Return validation errors without turning invalid metadata into an HTTP error."""
    client = TestClient(create_app())

    response = client.post(
        METADATA_VALIDATE_PATH,
        json={"kind": "adapter", "metadata": _invalid_adapter_document()},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["kind"] == "adapter"
    assert payload["is_valid"] is False
    assert payload["errors"]
    assert [check["name"] for check in payload["checks"]] == [
        "Croissant compliance",
        "Adapter schema",
        "Adapter semantics",
    ]


def test_validate_metadata_endpoint_validates_embedded_adapter_datasets() -> None:
    """Validate embedded datasets as part of the adapter metadata contract."""
    client = TestClient(create_app())
    metadata = _valid_adapter_document()
    embedded_dataset = metadata["hasPart"][0]
    assert isinstance(embedded_dataset, dict)
    embedded_dataset["@type"] = "Thing"

    response = client.post(
        METADATA_VALIDATE_PATH,
        json={"kind": "adapter", "metadata": metadata},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["kind"] == "adapter"
    assert payload["is_valid"] is False
    embedded_check = next(
        check
        for check in payload["checks"]
        if check["name"] == "Embedded dataset: Example dataset"
    )
    assert embedded_check["is_valid"] is False
    assert any("[Example dataset]" in error for error in embedded_check["errors"])


def test_validate_metadata_endpoint_rejects_unknown_auto_type() -> None:
    """Return 422 when auto detection cannot identify the metadata type."""
    client = TestClient(create_app())

    response = client.post(
        METADATA_VALIDATE_PATH,
        json={"metadata": {"name": "Unknown metadata"}},
    )

    assert response.status_code == 422
    assert "Could not detect metadata type automatically." in response.json()["detail"]


def test_validate_metadata_endpoint_rejects_invalid_kind() -> None:
    """Return request validation errors for unsupported metadata kinds."""
    client = TestClient(create_app())

    response = client.post(
        METADATA_VALIDATE_PATH,
        json={"kind": "unknown", "metadata": _valid_dataset_document()},
    )

    assert response.status_code == 422


# ===========================================================
# Metadata Dataset Generation Endpoint Tests
# ===========================================================


def test_generate_dataset_metadata_endpoint_returns_generated_document(
    monkeypatch,
    tmp_path,
) -> None:
    """Generate dataset metadata through the API without persisting it."""
    captured: dict[str, object] = {}

    def fake_execute_dataset_request(request, generator):
        captured["request"] = request
        captured["generator"] = generator
        document = _valid_dataset_document()
        Path(request.output_path).write_text(json.dumps(document), encoding="utf-8")
        return GenerationResult(
            output_path=request.output_path,
            stdout="generated",
            stderr="",
            document=document,
            warnings=["Missing license; using 'UNKNOWN'."],
        )

    monkeypatch.setattr(
        metadata_router,
        "execute_dataset_request",
        fake_execute_dataset_request,
    )
    client = TestClient(create_app())

    response = client.post(
        DATASET_GENERATE_PATH,
        json=_dataset_generate_payload(
            str(tmp_path),
            generator="native",
            name=" Example dataset ",
            license=" https://opensource.org/licenses/MIT ",
            validate=True,
        ),
    )

    assert response.status_code == 200
    payload = response.json()
    request = captured["request"]
    assert captured["generator"] == "native"
    assert request.input_path == str(tmp_path)
    assert request.name == "Example dataset"
    assert request.license_value == "https://opensource.org/licenses/MIT"
    assert payload["metadata"]["name"] == "Example dataset"
    assert payload["generator"] == "native"
    assert payload["stdout"] == "generated"
    assert payload["warnings"] == ["Missing license; using 'UNKNOWN'."]
    assert payload["validation"]["kind"] == "dataset"
    assert payload["validation"]["is_valid"] is True


def test_generate_dataset_metadata_endpoint_can_skip_validation(
    monkeypatch,
    tmp_path,
) -> None:
    """Allow clients to request generation without a validation payload."""

    def fake_execute_dataset_request(request, generator):
        document = _valid_dataset_document()
        return GenerationResult(
            output_path=request.output_path,
            document=document,
        )

    monkeypatch.setattr(
        metadata_router,
        "execute_dataset_request",
        fake_execute_dataset_request,
    )
    client = TestClient(create_app())

    response = client.post(
        DATASET_GENERATE_PATH,
        json=_dataset_generate_payload(str(tmp_path), validate=False),
    )

    assert response.status_code == 200
    assert response.json()["validation"] is None


def test_generate_dataset_metadata_endpoint_returns_generator_errors(
    monkeypatch,
    tmp_path,
) -> None:
    """Return 400 when the core generator cannot produce metadata."""

    def fake_execute_dataset_request(request, generator):
        raise RuntimeError("No supported dataset files were found.")

    monkeypatch.setattr(
        metadata_router,
        "execute_dataset_request",
        fake_execute_dataset_request,
    )
    client = TestClient(create_app())

    response = client.post(
        DATASET_GENERATE_PATH,
        json=_dataset_generate_payload(str(tmp_path)),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "No supported dataset files were found."


def test_generate_dataset_metadata_endpoint_rejects_blank_input_path() -> None:
    """Return 422 when the dataset input path is blank after normalization."""
    client = TestClient(create_app())

    response = client.post(
        DATASET_GENERATE_PATH,
        json=_dataset_generate_payload("   "),
    )

    assert response.status_code == 422


# ===========================================================
# Metadata Adapter Generation Endpoint Tests
# ===========================================================


def test_generate_adapter_metadata_endpoint_returns_generated_document(
    monkeypatch,
    tmp_path,
) -> None:
    """Generate adapter metadata through the API without persisting it."""
    captured: dict[str, object] = {}

    def fake_execute_adapter_request(request, generator):
        captured["request"] = request
        captured["generator"] = generator
        document = _valid_adapter_document()
        Path(request.output_path).write_text(json.dumps(document), encoding="utf-8")
        return GenerationResult(
            output_path=request.output_path,
            stdout="adapter generated",
            stderr="",
            document=document,
        )

    monkeypatch.setattr(
        metadata_router,
        "execute_adapter_request",
        fake_execute_adapter_request,
    )
    client = TestClient(create_app())

    response = client.post(
        ADAPTER_GENERATE_PATH,
        json=_adapter_generate_payload(
            name=" Example Adapter ",
            description=" Example adapter ",
            dataset_paths=[str(tmp_path / "dataset.jsonld")],
            generated_datasets=[
                {
                    "input": str(tmp_path / "data"),
                    "name": "Generated Dataset",
                    "license": "https://opensource.org/licenses/MIT",
                }
            ],
            creators=[
                "Person|Example Creator|Example Lab||https://example.org|https://orcid.org/0000-0000-0000-0000"
            ],
            keywords=["adapter", "biocypher"],
            dataset_generator="native",
            validate=True,
        ),
    )

    assert response.status_code == 200
    payload = response.json()
    request = captured["request"]
    assert captured["generator"] == "native"
    assert request.name == "Example Adapter"
    assert request.dataset_paths == [str(tmp_path / "dataset.jsonld")]
    assert request.dataset_generator == "native"
    assert request.generated_datasets[0].input_path == str(tmp_path / "data")
    assert request.generated_datasets[0].name == "Generated Dataset"
    assert payload["metadata"]["name"] == "Example Adapter"
    assert payload["generator"] == "native"
    assert payload["dataset_generator"] == "native"
    assert payload["stdout"] == "adapter generated"
    assert payload["validation"]["kind"] == "adapter"
    assert payload["validation"]["is_valid"] is True


def test_generate_adapter_metadata_endpoint_can_skip_validation(
    monkeypatch,
    tmp_path,
) -> None:
    """Allow clients to request adapter generation without validation output."""

    def fake_execute_adapter_request(request, generator):
        return GenerationResult(
            output_path=request.output_path,
            document=_valid_adapter_document(),
        )

    monkeypatch.setattr(
        metadata_router,
        "execute_adapter_request",
        fake_execute_adapter_request,
    )
    client = TestClient(create_app())

    response = client.post(
        ADAPTER_GENERATE_PATH,
        json=_adapter_generate_payload(
            dataset_paths=[str(tmp_path / "dataset.jsonld")],
            validate=False,
        ),
    )

    assert response.status_code == 200
    assert response.json()["validation"] is None


def test_generate_adapter_metadata_endpoint_returns_generator_errors(
    monkeypatch,
    tmp_path,
) -> None:
    """Return 400 when the adapter generator cannot produce metadata."""

    def fake_execute_adapter_request(request, generator):
        raise RuntimeError("Dataset metadata file does not exist.")

    monkeypatch.setattr(
        metadata_router,
        "execute_adapter_request",
        fake_execute_adapter_request,
    )
    client = TestClient(create_app())

    response = client.post(
        ADAPTER_GENERATE_PATH,
        json=_adapter_generate_payload(
            dataset_paths=[str(tmp_path / "missing.jsonld")],
        ),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Dataset metadata file does not exist."


def test_generate_adapter_metadata_endpoint_rejects_blank_required_lists() -> None:
    """Return 422 when required list fields contain only blank values."""
    client = TestClient(create_app())

    response = client.post(
        ADAPTER_GENERATE_PATH,
        json=_adapter_generate_payload(
            creators=["   "],
            keywords=[""],
        ),
    )

    assert response.status_code == 422


def test_generate_adapter_metadata_endpoint_runs_real_native_generator(
    tmp_path,
) -> None:
    """Generate adapter metadata through the real native adapter and dataset stack."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "people.csv").write_text("id,name\n1,Alice\n2,Bob\n", encoding="utf-8")
    client = TestClient(create_app())

    response = client.post(
        ADAPTER_GENERATE_PATH,
        json=_adapter_generate_payload(
            name="People Adapter",
            description="Adapter metadata generated through the API.",
            code_repository="https://github.com/example/people-adapter",
            creators=[
                "Person|Example Creator|Example Lab|||https://orcid.org/0000-0000-0000-0000"
            ],
            keywords=["adapter", "biocypher"],
            dataset_generator="native",
            generated_datasets=[
                {
                    "input": str(data_dir),
                    "name": "People Dataset",
                    "description": "Small people dataset.",
                    "url": "https://example.org/people",
                    "license": "https://opensource.org/licenses/MIT",
                    "citation": "https://example.org/people",
                    "dataset_version": "1.0.0",
                    "date_published": "2026-04-17",
                    "creators": ["Person|Dataset Creator"],
                }
            ],
            validate=True,
        ),
    )

    assert response.status_code == 200
    payload = response.json()
    metadata = payload["metadata"]
    assert metadata["@type"] == "SoftwareSourceCode"
    assert metadata["name"] == "People Adapter"
    assert metadata["hasPart"][0]["name"] == "People Dataset"
    assert metadata["hasPart"][0]["distribution"][0]["name"] == "people.csv"
    assert payload["generator"] == "native"
    assert payload["dataset_generator"] == "native"
    assert payload["validation"]["kind"] == "adapter"
    assert payload["validation"]["is_valid"] is True


def test_metadata_generation_openapi_examples_are_available() -> None:
    """Keep copy-ready request examples available in the Swagger UI."""
    schema = create_app().openapi()
    schemas = schema["components"]["schemas"]

    dataset_example = schemas["DatasetMetadataGenerateRequest"]["example"]
    adapter_example = schemas["AdapterMetadataGenerateRequest"]["example"]
    validation_example = schemas["MetadataValidationRequest"]["example"]

    assert dataset_example == DATASET_METADATA_GENERATE_EXAMPLE
    assert adapter_example == ADAPTER_METADATA_GENERATE_EXAMPLE
    assert validation_example == METADATA_VALIDATE_DATASET_EXAMPLE
