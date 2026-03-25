from __future__ import annotations

import json
from pathlib import Path
import re

from typer.testing import CliRunner

from cli import app


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


def test_finish_registration_command_rejects_duplicate_valid_adapter(
    tmp_path: Path,
) -> None:
    """Reject finishing a second valid adapter with the same uniqueness key."""
    database_path = tmp_path / "registry.sqlite3"
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()
    (repo_a / "croissant.jsonld").write_text(
        json.dumps(_valid_adapter_document()),
        encoding="utf-8",
    )
    (repo_b / "croissant.jsonld").write_text(
        json.dumps(_valid_adapter_document()),
        encoding="utf-8",
    )

    first = runner.invoke(
        app,
        [
            "submit-registration",
            "--name",
            "Example Adapter",
            str(repo_a),
            "--db-path",
            str(database_path),
        ],
    )
    second = runner.invoke(
        app,
        [
            "submit-registration",
            "--name",
            "Example Adapter",
            str(repo_b),
            "--db-path",
            str(database_path),
        ],
    )

    def extract_registration_id(output: str) -> str:
        match = re.search(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            output,
        )
        if match is not None:
            return match.group(0)
        raise AssertionError(f"Registration ID not found in output: {output}")

    first_id = extract_registration_id(first.output)
    second_id = extract_registration_id(second.output)

    first_finish = runner.invoke(
        app,
        ["finish-registration", first_id, "--db-path", str(database_path)],
    )
    duplicate_finish = runner.invoke(
        app,
        ["finish-registration", second_id, "--db-path", str(database_path)],
    )

    assert first_finish.exit_code == 0, first_finish.output
    assert duplicate_finish.exit_code == 1
    assert "Duplicate registration rejected" in duplicate_finish.output
