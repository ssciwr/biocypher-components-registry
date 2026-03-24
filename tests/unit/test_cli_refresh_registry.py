from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from cli import app


runner = CliRunner()


def _valid_adapter_document(
    *,
    adapter_id: str = "example-adapter",
    name: str = "Example Adapter",
    version: str = "1.0.0",
) -> dict:
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
        "@type": "SoftwareSourceCode",
        "@id": adapter_id,
        "name": name,
        "description": "Adapter description",
        "conformsTo": "https://bioschemas.org/profiles/ComputationalTool/1.0-RELEASE/",
        "version": version,
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
        "hasPart": [
            {
                "@type": "sc:Dataset",
                "name": "Example dataset",
                "description": "Example dataset",
                "conformsTo": "http://mlcommons.org/croissant/1.0",
                "citeAs": "https://example.org/dataset",
                "creator": [{"@type": "sc:Person", "name": "Example Creator"}],
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
        ],
    }


def test_refresh_registry_command_processes_active_sources_and_reports_summary(
    tmp_path: Path,
) -> None:
    """Run one batch refresh from the CLI and print the outcome summary."""
    database_path = tmp_path / "registry.sqlite3"
    valid_repo = tmp_path / "valid-repo"
    invalid_repo = tmp_path / "invalid-repo"
    valid_repo.mkdir()
    invalid_repo.mkdir()
    (valid_repo / "croissant.jsonld").write_text(
        json.dumps(
            _valid_adapter_document(
                adapter_id="batch-valid-adapter",
                name="Batch Valid Adapter",
                version="1.0.0",
            )
        ),
        encoding="utf-8",
    )
    invalid_document = _valid_adapter_document(
        adapter_id="batch-invalid-adapter",
        name="Batch Invalid Adapter",
        version="1.0.0",
    )
    invalid_document.pop("version")
    (invalid_repo / "croissant.jsonld").write_text(
        json.dumps(invalid_document),
        encoding="utf-8",
    )

    submit_valid = runner.invoke(
        app,
        [
            "submit-registration",
            "--name",
            "Batch Valid Adapter",
            str(valid_repo),
            "--db-path",
            str(database_path),
        ],
    )
    submit_invalid = runner.invoke(
        app,
        [
            "submit-registration",
            "--name",
            "Batch Invalid Adapter",
            str(invalid_repo),
            "--db-path",
            str(database_path),
        ],
    )

    assert submit_valid.exit_code == 0, submit_valid.output
    assert submit_invalid.exit_code == 0, submit_invalid.output

    result = runner.invoke(
        app,
        [
            "refresh-registry",
            "--db-path",
            str(database_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Batch Refresh Summary" in result.output
    assert "Active sources" in result.output
    assert "Processed" in result.output
    assert "VALID_CREATED" in result.output
    assert "INVALID" in result.output
    assert "Batch refresh finished" in result.output

    latest = runner.invoke(
        app,
        [
            "show-latest-refresh",
            "--db-path",
            str(database_path),
        ],
    )

    assert latest.exit_code == 0, latest.output
    assert "Latest Batch Refresh" in latest.output
    assert "Batch Refresh Summary" in latest.output
    assert "VALID_CREATED" in latest.output


def test_show_latest_refresh_command_rejects_missing_refresh(tmp_path: Path) -> None:
    """Report a clear error when no refresh has been recorded."""
    database_path = tmp_path / "registry.sqlite3"

    result = runner.invoke(
        app,
        [
            "show-latest-refresh",
            "--db-path",
            str(database_path),
        ],
    )

    assert result.exit_code == 1
    assert "No registry refresh has been recorded." in result.output
