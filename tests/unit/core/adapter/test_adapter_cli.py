from __future__ import annotations

import json
from pathlib import Path

import typer
from typer.testing import CliRunner

from cli import app
from src.core.adapter import cli as adapter_cli
from src.core.adapter.request import AdapterGenerationRequest
from src.core.dataset.request import GenerationRequest


runner = CliRunner()


def _valid_dataset_document() -> dict:
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


def test_adapter_direct_command_generates_adapter(tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset.jsonld"
    output_path = tmp_path / "adapter.jsonld"
    dataset_path.write_text(json.dumps(_valid_dataset_document()), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "adapter",
            "direct",
            "--output",
            str(output_path),
            "--name",
            "Example Adapter",
            "--description",
            "Adapter description",
            "--version",
            "1.0.0",
            "--license",
            "MIT",
            "--code-repository",
            "https://example.org/repo",
            "--dataset-path",
            str(dataset_path),
            "--creator",
            "Edwin Carreno, SSC, https://orcid.org/0000-0000-0000-0000",
            "--keywords",
            "adapter,biocypher",
        ],
    )

    assert result.exit_code == 0, result.output
    assert output_path.exists()
    assert "Adapter Ready" in result.output


def test_adapter_direct_command_still_accepts_pipe_creators(tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset.jsonld"
    output_path = tmp_path / "adapter.jsonld"
    dataset_path.write_text(json.dumps(_valid_dataset_document()), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "adapter",
            "direct",
            "--output",
            str(output_path),
            "--name",
            "Example Adapter",
            "--description",
            "Adapter description",
            "--version",
            "1.0.0",
            "--license",
            "MIT",
            "--code-repository",
            "https://example.org/repo",
            "--dataset-path",
            str(dataset_path),
            "--creator",
            "Edwin Carreno|SSC|https://orcid.org/0000-0000-0000-0000",
            "--keywords",
            "adapter,biocypher",
        ],
    )

    assert result.exit_code == 0, result.output
    assert output_path.exists()


def test_adapter_direct_requires_creator(tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset.jsonld"
    dataset_path.write_text(json.dumps(_valid_dataset_document()), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "adapter",
            "direct",
            "--name",
            "Example Adapter",
            "--description",
            "Adapter description",
            "--version",
            "1.0.0",
            "--license",
            "MIT",
            "--code-repository",
            "https://example.org/repo",
            "--dataset-path",
            str(dataset_path),
            "--keywords",
            "adapter",
        ],
    )

    assert result.exit_code != 0
    assert "At least one --creator is required" in result.output


def test_adapter_direct_accepts_auto_as_dataset_generator(tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset.jsonld"
    output_path = tmp_path / "adapter.jsonld"
    dataset_path.write_text(json.dumps(_valid_dataset_document()), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "adapter",
            "direct",
            "--dataset-generator",
            "auto",
            "--output",
            str(output_path),
            "--name",
            "Example Adapter",
            "--description",
            "Adapter description",
            "--version",
            "1.0.0",
            "--license",
            "MIT",
            "--code-repository",
            "https://example.org/repo",
            "--dataset-path",
            str(dataset_path),
            "--creator",
            "Edwin Carreno, SSC, https://orcid.org/0000-0000-0000-0000",
            "--keywords",
            "adapter,biocypher",
        ],
    )

    assert result.exit_code == 0, result.output
    assert output_path.exists()


def test_adapter_direct_rejects_removed_generator_flag(tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset.jsonld"
    dataset_path.write_text(json.dumps(_valid_dataset_document()), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "adapter",
            "direct",
            "--generator",
            "auto",
            "--name",
            "Example Adapter",
            "--description",
            "Adapter description",
            "--version",
            "1.0.0",
            "--license",
            "MIT",
            "--code-repository",
            "https://example.org/repo",
            "--dataset-path",
            str(dataset_path),
            "--creator",
            "Edwin Carreno, SSC, https://orcid.org/0000-0000-0000-0000",
            "--keywords",
            "adapter,biocypher",
        ],
    )

    assert result.exit_code != 0
    assert "--generator" in result.output


def test_adapter_guided_builds_request_and_runs(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_prompt_for_adapter_request(
        output_path: str,
        dataset_generator: str,
    ) -> AdapterGenerationRequest:
        captured["output_path"] = output_path
        captured["dataset_generator"] = dataset_generator
        return AdapterGenerationRequest(
            output_path=output_path,
            name="Example Adapter",
            description="Adapter description",
            version="1.0.0",
            license_value="MIT",
            code_repository="https://example.org/repo",
            dataset_paths=["dataset.jsonld"],
            validate=True,
            creators=["Edwin Carreno, SSC, https://orcid.org/0000-0000-0000-0000"],
            keywords=["adapter", "biocypher"],
            dataset_generator=dataset_generator,
        )

    def fake_execute_adapter_request(
        request: AdapterGenerationRequest,
        generator: str,
    ):
        captured["request"] = request
        captured["generator"] = generator

        class Result:
            stdout = "ok"
            stderr = ""

        return Result()

    monkeypatch.setattr(
        "src.core.adapter.cli.prompt_for_adapter_request",
        fake_prompt_for_adapter_request,
    )
    monkeypatch.setattr(
        "src.core.adapter.cli.execute_adapter_request",
        fake_execute_adapter_request,
    )

    result = runner.invoke(
        app,
        ["adapter", "guided", "--output", "guided-output.jsonld"],
    )

    assert result.exit_code == 0, result.output
    assert captured["output_path"] == "guided-output.jsonld"
    assert captured["dataset_generator"] == "croissant-baker"
    assert captured["generator"] == "native"


def test_adapter_guided_retries_after_backend_failure(monkeypatch) -> None:
    request = AdapterGenerationRequest(
        output_path="guided-output.jsonld",
        name="Example Adapter",
        description="initial",
        version="1.0.0",
        license_value="MIT",
        code_repository="https://example.org/repo",
        dataset_paths=["dataset.jsonld"],
        validate=True,
        creators=["Edwin Carreno, SSC, https://orcid.org/0000-0000-0000-0000"],
        keywords=["adapter", "biocypher"],
        dataset_generator="croissant-baker",
    )
    calls = {"count": 0}

    def fake_prompt_for_adapter_request(
        output_path: str,
        dataset_generator: str,
    ) -> AdapterGenerationRequest:
        return request

    def fake_execute_adapter_request(
        request: AdapterGenerationRequest,
        generator: str,
    ):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("backend failed")

        class Result:
            stdout = "ok"
            stderr = ""

        return Result()

    def fake_review_adapter_request(current_request: AdapterGenerationRequest) -> None:
        current_request.description = "fixed"

    confirm_values = iter([True])

    monkeypatch.setattr(
        "src.core.adapter.cli.prompt_for_adapter_request",
        fake_prompt_for_adapter_request,
    )
    monkeypatch.setattr(
        "src.core.adapter.cli.execute_adapter_request",
        fake_execute_adapter_request,
    )
    monkeypatch.setattr(
        "src.core.adapter.cli.review_adapter_request",
        fake_review_adapter_request,
    )
    monkeypatch.setattr(typer, "confirm", lambda *args, **kwargs: next(confirm_values))

    result = runner.invoke(
        app,
        ["adapter", "guided", "--output", "guided-output.jsonld"],
    )

    assert result.exit_code == 0, result.output
    assert calls["count"] == 2
    assert request.description == "fixed"


def test_adapter_direct_supports_generated_dataset_configs(tmp_path: Path, monkeypatch) -> None:
    dataset_config = tmp_path / "dataset.yaml"
    dataset_config.write_text("input: /tmp/data\n", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_dataset_request_from_config(config_path: str) -> GenerationRequest:
        captured["config_path"] = config_path
        return GenerationRequest(input_path="/tmp/data", output_path="croissant.jsonld")

    def fake_execute_adapter_request(
        request: AdapterGenerationRequest,
        generator: str,
    ):
        captured["request"] = request
        captured["generator"] = generator

        class Result:
            stdout = "ok"
            stderr = ""

        return Result()

    monkeypatch.setattr(
        "src.core.adapter.cli.dataset_request_from_config",
        fake_dataset_request_from_config,
    )
    monkeypatch.setattr(
        "src.core.adapter.cli.execute_adapter_request",
        fake_execute_adapter_request,
    )

    result = runner.invoke(
        app,
        [
            "adapter",
            "direct",
            "--name",
            "Example Adapter",
            "--description",
            "Adapter description",
            "--version",
            "1.0.0",
            "--license",
            "MIT",
            "--code-repository",
            "https://example.org/repo",
            "--dataset-config",
            str(dataset_config),
            "--creator",
            "Edwin Carreno, SSC, https://orcid.org/0000-0000-0000-0000",
            "--keywords",
            "adapter,biocypher",
        ],
    )

    assert result.exit_code == 0, result.output
    request = captured["request"]
    assert isinstance(request, AdapterGenerationRequest)
    assert request.dataset_generator == "croissant-baker"
    assert len(request.generated_datasets) == 1


def test_parse_dataset_blocks_builds_multiple_generated_datasets() -> None:
    datasets = adapter_cli._parse_dataset_blocks(
        [
            "--dataset",
            "--input",
            "data/in/sample_networks_omnipath.tsv",
            "--dataset-name",
            "Networks",
            "--dataset-description",
            "Network interactions",
            "--dataset-license",
            "MIT",
            "--dataset-url",
            "https://omnipathdb.org/",
            "--dataset-version",
            "1.0.0",
            "--dataset-date-published",
            "2016-06-01",
            "--dataset-citation",
            "https://omnipathdb.org/",
            "--dataset-creator",
            "Saezlab,,https://www.saezlab.com/",
            "--dataset",
            "--dataset-input",
            "data/in/sample_intercell.tsv",
            "--dataset-name",
            "Intercell",
            "--dataset-description",
            "Intercell roles",
            "--dataset-license",
            "MIT",
            "--dataset-url",
            "https://omnipathdb.org/",
            "--dataset-version",
            "1.0.0",
            "--dataset-date-published",
            "2016-06-05",
            "--dataset-citation",
            "https://omnipathdb.org/",
            "--dataset-creator",
            "Saezlab,,https://www.saezlab.com/",
        ]
    )

    assert len(datasets) == 2
    assert datasets[0].input_path == "data/in/sample_networks_omnipath.tsv"
    assert datasets[0].name == "Networks"
    assert datasets[1].input_path == "data/in/sample_intercell.tsv"
    assert datasets[1].name == "Intercell"


def test_adapter_direct_supports_inline_dataset_blocks(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_execute_adapter_request(
        request: AdapterGenerationRequest,
        generator: str,
    ):
        captured["request"] = request
        captured["generator"] = generator

        class Result:
            stdout = "ok"
            stderr = ""

        return Result()

    monkeypatch.setattr(
        "src.core.adapter.cli.execute_adapter_request",
        fake_execute_adapter_request,
    )

    result = runner.invoke(
        app,
        [
            "adapter",
            "direct",
            "--dataset-generator",
            "auto",
            "--output",
            "adapter.jsonld",
            "--name",
            "OmniPath Adapter",
            "--description",
            "Adapter description",
            "--version",
            "1.0.0",
            "--license",
            "MIT",
            "--code-repository",
            "https://example.org/repo",
            "--creator",
            "Edwin Carreno, SSC, https://orcid.org/0000-0000-0000-0000",
            "--keywords",
            "adapter,biocypher",
            "--dataset",
            "--input",
            "data/in/sample_networks_omnipath.tsv",
            "--dataset-name",
            "Networks",
            "--dataset-description",
            "Network interactions",
            "--dataset-license",
            "MIT",
            "--dataset-url",
            "https://omnipathdb.org/",
            "--dataset-version",
            "1.0.0",
            "--dataset-date-published",
            "2016-06-01",
            "--dataset-citation",
            "https://omnipathdb.org/",
            "--dataset-creator",
            "Saezlab,,https://www.saezlab.com/",
            "--dataset",
            "--input",
            "data/in/sample_intercell.tsv",
            "--dataset-name",
            "Intercell",
            "--dataset-description",
            "Intercell roles",
            "--dataset-license",
            "MIT",
            "--dataset-url",
            "https://omnipathdb.org/",
            "--dataset-version",
            "1.0.0",
            "--dataset-date-published",
            "2016-06-05",
            "--dataset-citation",
            "https://omnipathdb.org/",
            "--dataset-creator",
            "Saezlab,,https://www.saezlab.com/",
        ],
    )

    assert result.exit_code == 0, result.output
    request = captured["request"]
    assert isinstance(request, AdapterGenerationRequest)
    assert captured["generator"] == "native"
    assert request.dataset_generator == "auto"
    assert len(request.generated_datasets) == 2
    assert request.generated_datasets[0].name == "Networks"
    assert request.generated_datasets[1].name == "Intercell"


def test_adapter_config_builds_request_and_runs(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "adapter.yaml"
    config_path.write_text(
        """
adapter:
  name: Example Adapter
  description: Adapter description
  version: 1.0.0
  license: MIT
  code_repository: https://example.org/repo
  creators:
    - "Edwin Carreno, SSC, https://orcid.org/0000-0000-0000-0000"
  keywords:
    - adapter
    - biocypher
datasets:
  - mode: existing
    path: dataset.jsonld
        """.strip(),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_execute_adapter_request(
        request: AdapterGenerationRequest,
        generator: str,
    ):
        captured["request"] = request
        captured["generator"] = generator

        class Result:
            stdout = "ok"
            stderr = ""

        return Result()

    monkeypatch.setattr(
        "src.core.adapter.cli.execute_adapter_request",
        fake_execute_adapter_request,
    )

    result = runner.invoke(
        app,
        [
            "adapter",
            "config",
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code == 0, result.output
    request = captured["request"]
    assert isinstance(request, AdapterGenerationRequest)
    assert request.dataset_generator == "croissant-baker"
    assert request.dataset_paths == ["dataset.jsonld"]
