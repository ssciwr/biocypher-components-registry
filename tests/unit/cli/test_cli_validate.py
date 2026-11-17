from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from typer.testing import CliRunner

from cli import app
from src.core.adapter.document import build_adapter_creator, build_adapter_document
from src.core.shared.constants import STANDARD_CONTEXT

runner = CliRunner()


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


def _valid_adapter_document() -> dict:
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


def test_validate_auto_detects_dataset_metadata(tmp_path: Path) -> None:
    dataset_path = tmp_path / "croissant.jsonld"
    dataset_path.write_text(
        json.dumps(_valid_dataset_document()),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["validate", str(dataset_path)])

    assert result.exit_code == 0, result.output
    assert "Validation Target" in result.output
    assert "Validation Checks" in result.output
    assert "Croissant compliance" in result.output
    assert "Detected Type" in result.output
    assert "VALID" in result.output
    assert "dataset metadata" in result.output


def test_validate_adapter_command_rejects_dataset_root(tmp_path: Path) -> None:
    dataset_path = tmp_path / "croissant.jsonld"
    dataset_path.write_text(json.dumps(_valid_dataset_document()), encoding="utf-8")

    result = runner.invoke(app, ["validate-adapter", str(dataset_path)])

    assert result.exit_code == 1
    assert "Validation Target" in result.output
    assert "Validation Checks" in result.output
    assert "Croissant compliance" in result.output
    assert "Adapter schema" in result.output
    assert "adapter" in result.output
    assert "INVALID" in result.output
    assert "adapter metadata" in result.output


def test_validate_adapter_command_validates_embedded_datasets(tmp_path: Path) -> None:
    metadata_path = tmp_path / "croissant.jsonld"
    metadata = _valid_adapter_document()
    metadata["hasPart"][0]["@type"] = "Thing"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    result = runner.invoke(app, ["validate-adapter", str(metadata_path)])

    assert result.exit_code == 1
    assert "Embedded dataset: Example dataset" in result.output
    assert "[Example dataset]" in result.output
    assert "INVALID" in result.output


def test_validate_reports_loader_errors_cleanly(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.jsonld"

    result = runner.invoke(app, ["validate", str(missing_path)])

    assert result.exit_code == 1
    assert "Path not found" in result.output


def test_validate_rejects_unknown_root_type(tmp_path: Path) -> None:
    metadata_path = tmp_path / "croissant.jsonld"
    metadata = _valid_dataset_document()
    metadata.pop("@type", None)
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    result = runner.invoke(app, ["validate", str(metadata_path)])

    assert result.exit_code == 2
    assert "Could not detect metadata type automatically" in result.output
