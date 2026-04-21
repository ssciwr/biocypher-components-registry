from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.dependencies import get_registration_store
from src.core.registration.service import submit_registration
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore


# ===========================================================
# Registry Endpoint Tests
# ===========================================================


def _valid_adapter_document(
    *,
    adapter_id: str = "example-adapter",
    name: str = "Example Adapter",
    version: str = "1.0.0",
) -> dict[str, object]:
    """Return a valid adapter metadata document for refresh tests."""
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


def _create_registry_client(
    store: SQLiteRegistrationStore,
) -> TestClient:
    """Create an API test client with an overridden registration store."""
    app = create_app()
    app.dependency_overrides[get_registration_store] = lambda: store
    return TestClient(app)


def test_list_registry_registrations_endpoint_returns_empty_list(
    tmp_path: Path,
) -> None:
    """Return an empty registry registration list when no active registrations exist."""
    database_path = tmp_path / "registry.sqlite3"
    store = SQLiteRegistrationStore(database_path)
    client = _create_registry_client(store)

    response = client.get("/api/v1/registry/registrations")

    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_list_registry_registrations_endpoint_returns_latest_event_type(
    tmp_path: Path,
) -> None:
    """Return registry registrations with status and latest event information."""
    database_path = tmp_path / "registry.sqlite3"
    valid_repo = tmp_path / "valid-repo"
    invalid_repo = tmp_path / "invalid-repo"
    missing_repo = tmp_path / "missing-repo"
    valid_repo.mkdir()
    invalid_repo.mkdir()
    missing_repo.mkdir()
    (valid_repo / "croissant.jsonld").write_text(
        json.dumps(
            _valid_adapter_document(
                adapter_id="valid-adapter",
                name="Valid Adapter",
            )
        ),
        encoding="utf-8",
    )
    invalid_document = _valid_adapter_document(
        adapter_id="invalid-adapter",
        name="Invalid Adapter",
    )
    invalid_document.pop("version")
    (invalid_repo / "croissant.jsonld").write_text(
        json.dumps(invalid_document),
        encoding="utf-8",
    )
    store = SQLiteRegistrationStore(database_path)
    valid = submit_registration("Valid Adapter", str(valid_repo), store)
    invalid = submit_registration("Invalid Adapter", str(invalid_repo), store)
    missing = submit_registration("Missing Adapter", str(missing_repo), store)
    client = _create_registry_client(store)
    refresh_response = client.post("/api/v1/registry/refreshes")
    assert refresh_response.status_code == 200

    response = client.get("/api/v1/registry/registrations")

    assert response.status_code == 200
    payload = response.json()
    assert [item["registration_id"] for item in payload["items"]] == [
        valid.registration_id,
        invalid.registration_id,
        missing.registration_id,
    ]
    assert [item["status"] for item in payload["items"]] == [
        "VALID",
        "INVALID",
        "SUBMITTED",
    ]
    assert [item["latest_event_type"] for item in payload["items"]] == [
        "VALID_CREATED",
        "INVALID_SCHEMA",
        "FETCH_FAILED",
    ]
    assert all("metadata" not in item for item in payload["items"])


def test_list_registry_registrations_endpoint_filters_by_status_and_latest_event(
    tmp_path: Path,
) -> None:
    """Filter active registry sources by status and latest event type."""
    database_path = tmp_path / "registry.sqlite3"
    valid_repo = tmp_path / "valid-repo"
    invalid_repo = tmp_path / "invalid-repo"
    valid_repo.mkdir()
    invalid_repo.mkdir()
    (valid_repo / "croissant.jsonld").write_text(
        json.dumps(
            _valid_adapter_document(
                adapter_id="valid-adapter",
                name="Valid Adapter",
            )
        ),
        encoding="utf-8",
    )
    invalid_document = _valid_adapter_document(
        adapter_id="invalid-adapter",
        name="Invalid Adapter",
    )
    invalid_document.pop("version")
    (invalid_repo / "croissant.jsonld").write_text(
        json.dumps(invalid_document),
        encoding="utf-8",
    )
    store = SQLiteRegistrationStore(database_path)
    submit_registration("Valid Adapter", str(valid_repo), store)
    invalid = submit_registration("Invalid Adapter", str(invalid_repo), store)
    client = _create_registry_client(store)
    refresh_response = client.post("/api/v1/registry/refreshes")
    assert refresh_response.status_code == 200

    response = client.get(
        "/api/v1/registry/registrations",
        params={"status": "INVALID", "latest_event": "INVALID_SCHEMA"},
    )

    assert response.status_code == 200
    assert [item["registration_id"] for item in response.json()["items"]] == [
        invalid.registration_id,
    ]


def test_list_registry_registrations_endpoint_rejects_unknown_filters(
    tmp_path: Path,
) -> None:
    """Reject unsupported registry registration filter values."""
    database_path = tmp_path / "registry.sqlite3"
    store = SQLiteRegistrationStore(database_path)
    client = _create_registry_client(store)

    response = client.get(
        "/api/v1/registry/registrations",
        params={"status": "missing", "latest_event": "missing"},
    )

    assert response.status_code == 422


def test_list_registry_entries_endpoint_returns_canonical_entries(
    tmp_path: Path,
) -> None:
    """Return valid canonical registry entries without full metadata payloads."""
    database_path = tmp_path / "registry.sqlite3"
    repository = tmp_path / "valid-repo"
    repository.mkdir()
    (repository / "croissant.jsonld").write_text(
        json.dumps(
            _valid_adapter_document(
                adapter_id="valid-adapter",
                name="Valid Adapter",
            )
        ),
        encoding="utf-8",
    )
    store = SQLiteRegistrationStore(database_path)
    submitted = submit_registration("Valid Adapter", str(repository), store)
    client = _create_registry_client(store)
    refresh_response = client.post("/api/v1/registry/refreshes")
    assert refresh_response.status_code == 200

    response = client.get("/api/v1/registry/entries")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert item["source_id"] == submitted.registration_id
    assert item["adapter_name"] == "Valid Adapter"
    assert item["adapter_version"] == "1.0.0"
    assert item["profile_version"] == "v1"
    assert item["uniqueness_key"] == "valid-adapter::1.0.0"
    assert item["metadata_checksum"]
    assert item["is_active"] is True
    assert "metadata" not in item


def test_list_registry_entries_endpoint_returns_empty_list_without_valid_entries(
    tmp_path: Path,
) -> None:
    """Return an empty entry list when no valid canonical entries exist."""
    database_path = tmp_path / "registry.sqlite3"
    store = SQLiteRegistrationStore(database_path)
    client = _create_registry_client(store)

    response = client.get("/api/v1/registry/entries")

    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_get_registry_entry_endpoint_returns_canonical_entry(
    tmp_path: Path,
) -> None:
    """Return one canonical valid registry entry by identifier."""
    database_path = tmp_path / "registry.sqlite3"
    repository = tmp_path / "valid-repo"
    repository.mkdir()
    (repository / "croissant.jsonld").write_text(
        json.dumps(
            _valid_adapter_document(
                adapter_id="valid-adapter",
                name="Valid Adapter",
            )
        ),
        encoding="utf-8",
    )
    store = SQLiteRegistrationStore(database_path)
    submitted = submit_registration("Valid Adapter", str(repository), store)
    client = _create_registry_client(store)
    refresh_response = client.post("/api/v1/registry/refreshes")
    assert refresh_response.status_code == 200
    entry_id = store.list_registry_entries()[0].entry_id

    response = client.get(f"/api/v1/registry/entries/{entry_id}")

    assert response.status_code == 200
    item = response.json()
    assert item["entry_id"] == entry_id
    assert item["source_id"] == submitted.registration_id
    assert item["adapter_name"] == "Valid Adapter"
    assert item["adapter_version"] == "1.0.0"
    assert item["profile_version"] == "v1"
    assert item["uniqueness_key"] == "valid-adapter::1.0.0"
    assert item["metadata_checksum"]
    assert "metadata" not in item


def test_get_registry_entry_endpoint_returns_not_found_for_unknown_entry(
    tmp_path: Path,
) -> None:
    """Return 404 when a canonical registry entry identifier is unknown."""
    database_path = tmp_path / "registry.sqlite3"
    store = SQLiteRegistrationStore(database_path)
    client = _create_registry_client(store)

    response = client.get("/api/v1/registry/entries/missing-entry")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Registry entry not found: missing-entry",
    }


def test_refresh_registry_endpoint_processes_active_sources(
    tmp_path: Path,
) -> None:
    """Process active registrations and return the batch summary."""
    database_path = tmp_path / "registry.sqlite3"
    valid_repo = tmp_path / "valid-repo"
    invalid_repo = tmp_path / "invalid-repo"
    missing_repo = tmp_path / "missing-repo"
    valid_repo.mkdir()
    invalid_repo.mkdir()
    missing_repo.mkdir()
    (valid_repo / "croissant.jsonld").write_text(
        json.dumps(
            _valid_adapter_document(
                adapter_id="valid-adapter",
                name="Valid Adapter",
            )
        ),
        encoding="utf-8",
    )
    invalid_document = _valid_adapter_document(
        adapter_id="invalid-adapter",
        name="Invalid Adapter",
    )
    invalid_document.pop("version")
    (invalid_repo / "croissant.jsonld").write_text(
        json.dumps(invalid_document),
        encoding="utf-8",
    )
    store = SQLiteRegistrationStore(database_path)
    submit_registration("Valid Adapter", str(valid_repo), store)
    submit_registration("Invalid Adapter", str(invalid_repo), store)
    submit_registration("Missing Adapter", str(missing_repo), store)
    client = _create_registry_client(store)

    response = client.post("/api/v1/registry/refreshes")

    assert response.status_code == 200
    assert response.json() == {
        "active_sources": 3,
        "processed": 3,
        "valid_created": 1,
        "unchanged": 0,
        "invalid": 1,
        "duplicate": 0,
        "rejected_same_version_changed": 0,
        "fetch_failed": 1,
    }

    latest_response = client.get("/api/v1/registry/refreshes/latest")
    assert latest_response.status_code == 200
    latest_payload = latest_response.json()
    assert latest_payload["refresh_id"]
    assert latest_payload["active_sources"] == 3
    assert latest_payload["processed"] == 3
    assert latest_payload["valid_created"] == 1
    assert latest_payload["invalid"] == 1
    assert latest_payload["fetch_failed"] == 1
    assert latest_payload["started_at"] <= latest_payload["finished_at"]


def test_refresh_registry_endpoint_returns_empty_summary_without_active_sources(
    tmp_path: Path,
) -> None:
    """Return an empty refresh summary when no registrations exist."""
    database_path = tmp_path / "registry.sqlite3"
    store = SQLiteRegistrationStore(database_path)
    client = _create_registry_client(store)

    response = client.post("/api/v1/registry/refreshes")

    assert response.status_code == 200
    assert response.json() == {
        "active_sources": 0,
        "processed": 0,
        "valid_created": 0,
        "unchanged": 0,
        "invalid": 0,
        "duplicate": 0,
        "rejected_same_version_changed": 0,
        "fetch_failed": 0,
    }


def test_latest_registry_refresh_endpoint_returns_not_found_without_refresh(
    tmp_path: Path,
) -> None:
    """Return 404 when no registry refresh has been recorded."""
    database_path = tmp_path / "registry.sqlite3"
    store = SQLiteRegistrationStore(database_path)
    client = _create_registry_client(store)

    response = client.get("/api/v1/registry/refreshes/latest")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "No registry refresh has been recorded.",
    }
