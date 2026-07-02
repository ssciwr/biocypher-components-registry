from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from typer.testing import CliRunner

from cli import app
from src.core.shared.constants import STANDARD_CONTEXT
from tests.support.croissant_fixtures import sample_dataset_document


runner = CliRunner()


def _valid_adapter_document() -> dict:
    return {
        "@context": deepcopy(STANDARD_CONTEXT),
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


def test_discover_command_discovers_and_validates_local_repository(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "adapter-repo"
    repo_path.mkdir()
    (repo_path / "croissant.jsonld").write_text(
        json.dumps(_valid_adapter_document()),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["discover", str(repo_path)])

    assert result.exit_code == 0, result.output
    assert "Discovery Target" in result.output
    assert "Discovery succeeded" in result.output
    assert "Validation Checks" in result.output
    assert "VALID" in result.output
    assert "adapter metadata" in result.output


def test_discover_command_reports_ambiguous_metadata_files(tmp_path: Path) -> None:
    repo_path = tmp_path / "adapter-repo"
    repo_path.mkdir()
    (repo_path / "croissant.jsonld").write_text("{}", encoding="utf-8")
    nested = repo_path / "nested"
    nested.mkdir()
    (nested / "croissant.jsonld").write_text("{}", encoding="utf-8")

    result = runner.invoke(app, ["discover", str(repo_path)])

    assert result.exit_code == 1
    assert "Multiple 'croissant.jsonld' files found" in result.output


def test_discover_command_rejects_http_repository_url() -> None:
    result = runner.invoke(app, ["discover", "http://github.com/example/repo"])

    assert result.exit_code == 1
    assert "Only HTTPS repository URLs are supported" in result.output
