from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from cli import app
from src.core.registration.service import submit_registration
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore


runner = CliRunner()


def _valid_adapter_document() -> dict:
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


def test_finish_registration_command_marks_registration_valid(tmp_path: Path) -> None:
    """Finish one stored registration and persist it as valid."""
    database_path = tmp_path / "registry.sqlite3"
    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    (repository / "croissant.jsonld").write_text(
        json.dumps(_valid_adapter_document()),
        encoding="utf-8",
    )
    store = SQLiteRegistrationStore(database_path)
    registration = submit_registration(
        adapter_name="Example Adapter",
        repository_location=str(repository),
        store=store,
    )

    result = runner.invoke(
        app,
        [
            "finish-registration",
            registration.registration_id,
            "--db-path",
            str(database_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Registration Result" in result.output
    assert "VALID" in result.output
    assert "Registration finished" in result.output


def test_finish_registration_command_reports_invalid_registration(
    tmp_path: Path,
) -> None:
    """Print the invalid result and return a non-zero exit code."""
    database_path = tmp_path / "registry.sqlite3"
    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    invalid_document = _valid_adapter_document()
    invalid_document.pop("version")
    (repository / "croissant.jsonld").write_text(
        json.dumps(invalid_document),
        encoding="utf-8",
    )
    store = SQLiteRegistrationStore(database_path)
    registration = submit_registration(
        adapter_name="Example Adapter",
        repository_location=str(repository),
        store=store,
    )

    result = runner.invoke(
        app,
        [
            "finish-registration",
            registration.registration_id,
            "--db-path",
            str(database_path),
        ],
    )

    assert result.exit_code == 1
    assert "Registration Result" in result.output
    assert "INVALID" in result.output
    assert "version" in result.output
