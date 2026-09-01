from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from src.core.adapter.backends.native import NativeAdapterGenerator
from src.core.adapter.request import AdapterGenerationRequest
from src.core.dataset.request import GenerationRequest, GenerationResult
from src.core.shared.constants import STANDARD_CONTEXT


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


def test_native_adapter_generator_embeds_valid_dataset(tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset.jsonld"
    output_path = tmp_path / "adapter.jsonld"
    dataset_path.write_text(json.dumps(_valid_dataset_document()), encoding="utf-8")

    request = AdapterGenerationRequest(
        output_path=str(output_path),
        name="Example Adapter",
        description="Adapter description",
        version="1.0.0",
        license_value="MIT",
        code_repository="https://example.org/repo",
        dataset_paths=[str(dataset_path)],
        validate=True,
        creators=["Edwin Carreno|SSC|https://orcid.org/0000-0000-0000-0000"],
        keywords=["adapter", "biocypher"],
    )

    result = NativeAdapterGenerator().generate(request)

    assert output_path.exists()
    assert result.document is not None
    assert result.document["@type"] == "SoftwareSourceCode"
    assert result.document["hasPart"][0]["@type"] == "sc:Dataset"
    assert "Validation completed!" in result.stdout


def test_native_adapter_generator_normalizes_known_license_keyword(
    tmp_path: Path,
) -> None:
    dataset_path = tmp_path / "dataset.jsonld"
    output_path = tmp_path / "adapter.jsonld"
    dataset_path.write_text(json.dumps(_valid_dataset_document()), encoding="utf-8")

    request = AdapterGenerationRequest(
        output_path=str(output_path),
        name="Example Adapter",
        description="Adapter description",
        version="1.0.0",
        license_value="mit",
        code_repository="https://example.org/repo",
        dataset_paths=[str(dataset_path)],
        validate=False,
        creators=["Edwin Carreno, SSC, https://orcid.org/0000-0000-0000-0000"],
        keywords=["adapter", "biocypher"],
    )

    result = NativeAdapterGenerator().generate(request)

    assert result.document is not None
    assert result.document["license"] == "https://opensource.org/licenses/MIT"


def test_native_adapter_generator_keeps_unknown_license_keyword(tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset.jsonld"
    output_path = tmp_path / "adapter.jsonld"
    dataset_path.write_text(json.dumps(_valid_dataset_document()), encoding="utf-8")

    request = AdapterGenerationRequest(
        output_path=str(output_path),
        name="Example Adapter",
        description="Adapter description",
        version="1.0.0",
        license_value="Custom-License",
        code_repository="https://example.org/repo",
        dataset_paths=[str(dataset_path)],
        validate=False,
        creators=["Edwin Carreno, SSC, https://orcid.org/0000-0000-0000-0000"],
        keywords=["adapter", "biocypher"],
    )

    result = NativeAdapterGenerator().generate(request)

    assert result.document is not None
    assert result.document["license"] == "Custom-License"


def test_native_adapter_generator_namespaces_embedded_dataset_ids(
    tmp_path: Path,
) -> None:
    dataset_path_a = tmp_path / "dataset-a.jsonld"
    dataset_path_b = tmp_path / "dataset-b.jsonld"
    output_path = tmp_path / "adapter.jsonld"
    document = _valid_dataset_document()
    dataset_path_a.write_text(json.dumps(document), encoding="utf-8")
    dataset_path_b.write_text(json.dumps(document), encoding="utf-8")

    request = AdapterGenerationRequest(
        output_path=str(output_path),
        name="Example Adapter",
        description="Adapter description",
        version="1.0.0",
        license_value="MIT",
        code_repository="https://example.org/repo",
        dataset_paths=[str(dataset_path_a), str(dataset_path_b)],
        validate=False,
        creators=["Edwin Carreno, SSC, https://orcid.org/0000-0000-0000-0000"],
        keywords=["adapter", "biocypher"],
    )

    result = NativeAdapterGenerator().generate(request)

    assert result.document is not None
    first = result.document["hasPart"][0]
    second = result.document["hasPart"][1]
    assert first["distribution"][0]["@id"] != second["distribution"][0]["@id"]
    assert first["recordSet"][0]["@id"] != second["recordSet"][0]["@id"]


def test_native_adapter_generator_includes_generated_dataset_report(
    monkeypatch, tmp_path: Path
) -> None:
    output_path = tmp_path / "adapter.jsonld"

    def fake_execute_dataset_request(request: GenerationRequest, generator: str):
        return GenerationResult(
            output_path=request.output_path,
            stdout="Auto-selected generator: croissant-baker\nReason: detected only standard dataset inputs handled by croissant-baker.",
            stderr="",
            document=_valid_dataset_document(),
        )

    monkeypatch.setattr(
        "src.core.adapter.backends.native.execute_dataset_request",
        fake_execute_dataset_request,
    )

    request = AdapterGenerationRequest(
        output_path=str(output_path),
        name="Example Adapter",
        description="Adapter description",
        version="1.0.0",
        license_value="MIT",
        code_repository="https://example.org/repo",
        dataset_paths=[],
        validate=False,
        creators=["Edwin Carreno, SSC, https://orcid.org/0000-0000-0000-0000"],
        keywords=["adapter", "biocypher"],
        dataset_generator="auto",
        generated_datasets=[
            GenerationRequest(
                input_path="/data/example",
                output_path="",
                name="Generated Dataset",
            )
        ],
    )

    result = NativeAdapterGenerator().generate(request)

    assert "Generated dataset 'Generated Dataset'" in result.stdout
    assert "Auto-selected generator: croissant-baker" in result.stdout
