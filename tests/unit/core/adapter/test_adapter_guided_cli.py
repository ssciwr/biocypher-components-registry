from __future__ import annotations

import typer
from rich.panel import Panel

from src.core.adapter import cli as adapter_cli
from src.core.adapter.config import request_from_config as adapter_request_from_config
from src.core.dataset.request import GenerationRequest


def test_adapter_request_from_config_reads_top_level_validate(tmp_path) -> None:
    config_path = tmp_path / "adapter.yaml"
    config_path.write_text(
        """
dataset_generator: auto
validate: false
adapter:
  name: Example Adapter
  description: Adapter description
  version: 1.0.0
  license: MIT
  code_repository: https://example.org/repo
  keywords:
    - adapter
  creators:
    - name: Example Creator
      email: creator@example.org
datasets:
  - mode: existing
    path: /tmp/dataset.jsonld
""".strip(),
        encoding="utf-8",
    )

    request = adapter_request_from_config(str(config_path))

    assert request.validate is False
    assert request.dataset_generator == "auto"


def test_prompt_for_adapter_request_collects_existing_dataset_values(monkeypatch) -> None:
    prompt_values = iter(
        [
            "Example Adapter",
            "Adapter description",
            "1.0.0",
            "MIT",
            "https://example.org/repo",
            "out.jsonld",
            "croissant-baker",
            "adapter-id",
            "adapter,biocypher",
            "Edwin Carreno",
            "SSC",
            "https://orcid.org/0000-0000-0000-0000",
            "existing",
            "dataset-a.jsonld",
        ]
    )
    confirm_values = iter([True, False, False, True])

    monkeypatch.setattr(typer, "prompt", lambda *args, **kwargs: next(prompt_values))
    monkeypatch.setattr(typer, "confirm", lambda *args, **kwargs: next(confirm_values))

    request = adapter_cli.prompt_for_adapter_request(output_path="croissant.jsonld")

    assert request.name == "Example Adapter"
    assert request.output_path == "out.jsonld"
    assert request.creators == [
        "Edwin Carreno, SSC, https://orcid.org/0000-0000-0000-0000"
    ]
    assert request.dataset_paths == ["dataset-a.jsonld"]
    assert request.dataset_generator == "croissant-baker"
    assert request.generated_datasets == []
    assert request.keywords == ["adapter", "biocypher"]
    assert request.adapter_id == "adapter-id"


def test_prompt_for_adapter_request_defaults_adapter_id_from_name(monkeypatch) -> None:
    prompt_values = iter(
        [
            "Example Adapter",
            "Adapter description",
            "1.0.0",
            "MIT",
            "https://example.org/repo",
            "out.jsonld",
            "croissant-baker",
            "example-adapter",
            "adapter,biocypher",
            "Edwin Carreno",
            "SSC",
            "https://orcid.org/0000-0000-0000-0000",
            "existing",
            "dataset-a.jsonld",
        ]
    )
    confirm_values = iter([True, False, False, True])

    monkeypatch.setattr(typer, "prompt", lambda *args, **kwargs: next(prompt_values))
    monkeypatch.setattr(typer, "confirm", lambda *args, **kwargs: next(confirm_values))

    request = adapter_cli.prompt_for_adapter_request(output_path="croissant.jsonld")

    assert request.adapter_id == "example-adapter"


def test_prompt_for_adapter_request_collects_generated_dataset_values(monkeypatch) -> None:
    prompt_values = iter(
        [
            "Example Adapter",
            "Adapter description",
            "1.0.0",
            "MIT",
            "https://example.org/repo",
            "out.jsonld",
            "croissant-baker",
            "adapter-id",
            "adapter,biocypher",
            "Edwin Carreno",
            "SSC",
            "https://orcid.org/0000-0000-0000-0000",
            "generate",
            "/tmp/data",
            "Generated Dataset",
            "Generated description",
            "https://example.org/dataset",
            "MIT",
            "https://example.org/citation",
            "1.0.0",
            "2024-01-01",
            "Denes Turei",
            "denes@example.org",
            "https://example.org/denes",
        ]
    )
    confirm_values = iter(
        [
            True,   # validate
            False,  # add another creator
            True,   # add dataset creator
            False,  # add another dataset creator
            False,  # add another dataset
            True,   # review proceed
        ]
    )

    monkeypatch.setattr(typer, "prompt", lambda *args, **kwargs: next(prompt_values))
    monkeypatch.setattr(typer, "confirm", lambda *args, **kwargs: next(confirm_values))

    request = adapter_cli.prompt_for_adapter_request(output_path="croissant.jsonld")

    assert request.dataset_paths == []
    assert len(request.generated_datasets) == 1
    dataset = request.generated_datasets[0]
    assert isinstance(dataset, GenerationRequest)
    assert dataset.input_path == "/tmp/data"
    assert dataset.name == "Generated Dataset"
    assert dataset.creators == ["Denes Turei, denes@example.org, https://example.org/denes"]


def test_prompt_for_adapter_request_shows_metadata_panels(monkeypatch) -> None:
    prompt_values = iter(
        [
            "Example Adapter",
            "Adapter description",
            "1.0.0",
            "MIT",
            "https://example.org/repo",
            "out.jsonld",
            "croissant-baker",
            "adapter-id",
            "adapter,biocypher",
            "Edwin Carreno",
            "SSC",
            "https://orcid.org/0000-0000-0000-0000",
            "existing",
            "dataset-a.jsonld",
        ]
    )
    confirm_values = iter([True, False, False, True])
    printed: list[object] = []

    monkeypatch.setattr(typer, "prompt", lambda *args, **kwargs: next(prompt_values))
    monkeypatch.setattr(typer, "confirm", lambda *args, **kwargs: next(confirm_values))
    monkeypatch.setattr(adapter_cli.console, "print", lambda *args, **kwargs: printed.extend(args))

    adapter_cli.prompt_for_adapter_request(output_path="croissant.jsonld")

    panel_titles = [
        str(obj.renderable)
        for obj in printed
        if isinstance(obj, Panel)
    ]
    assert any("Adapter Metadata" in title for title in panel_titles)
    assert any("Embedded Dataset Metadata" in title for title in panel_titles)
