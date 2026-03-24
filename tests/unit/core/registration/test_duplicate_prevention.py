from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import pytest

from src.core.adapter.service import create_registration_request
from src.core.registration.errors import DuplicateRegistrationError
from src.core.registration.service import finish_registration, submit_registration
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore


def _valid_adapter_document(
    name: str = "Example Adapter",
    version: str = "1.0.0",
    adapter_id: str = "example-adapter",
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


def test_sqlite_store_rejects_duplicate_valid_uniqueness_key(tmp_path: Path) -> None:
    """Reject a second valid registration that reuses the same uniqueness key."""
    database_path = tmp_path / "registry.sqlite3"
    store = SQLiteRegistrationStore(database_path)
    repo_1 = tmp_path / "repo-1"
    repo_2 = tmp_path / "repo-2"
    repo_1.mkdir()
    repo_2.mkdir()
    first = store.create_registration(
        create_registration_request("OmniPath Adapter", str(repo_1))
    )
    second = store.create_registration(
        create_registration_request("omnipath adapter", str(repo_2))
    )

    store.mark_registration_valid(
        registration_id=first.registration_id,
        metadata={
            "@id": "omnipath-adapter",
            "name": "OmniPath Adapter",
            "version": "1.0.0",
        },
        metadata_path=None,
        profile_version="v1",
        uniqueness_key="omnipath-adapter::1.0.0",
        observed_checksum="checksum-a",
    )

    with pytest.raises(DuplicateRegistrationError):
        store.mark_registration_valid(
            registration_id=second.registration_id,
            metadata={
                "@id": "omnipath-adapter",
                "name": "OmniPath Adapter",
                "version": "1.0.0",
            },
            metadata_path=None,
            profile_version="v1",
            uniqueness_key="omnipath-adapter::1.0.0",
            observed_checksum="checksum-a",
        )

    with sqlite3.connect(database_path) as connection:
        duplicate_event = connection.execute(
            """
            SELECT source_id, event_type
            FROM registration_events
            WHERE source_id = ? AND event_type = 'DUPLICATE'
            """,
            (second.registration_id,),
        ).fetchone()

    assert duplicate_event == (second.registration_id, "DUPLICATE")


def test_finish_registration_rejects_duplicate_valid_adapter(tmp_path: Path) -> None:
    """Reject finishing a registration when names differ but adapter id plus version match."""
    database_path = tmp_path / "registry.sqlite3"
    store = SQLiteRegistrationStore(database_path)

    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()
    (repo_a / "croissant.jsonld").write_text(
        json.dumps(
            _valid_adapter_document(
                name="OmniPath Adapter",
                adapter_id="omnipath-adapter",
            )
        ),
        encoding="utf-8",
    )
    (repo_b / "croissant.jsonld").write_text(
        json.dumps(
            _valid_adapter_document(
                name="omnipath adapter",
                adapter_id="omnipath-adapter",
            )
        ),
        encoding="utf-8",
    )

    first = submit_registration("OmniPath Adapter", str(repo_a), store)
    second = submit_registration("omnipath adapter", str(repo_b), store)

    finish_registration(first.registration_id, store)

    with pytest.raises(DuplicateRegistrationError):
        finish_registration(second.registration_id, store)
