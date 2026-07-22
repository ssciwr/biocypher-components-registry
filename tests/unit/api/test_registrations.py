from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.dependencies import get_optional_auth_session, get_registration_store
from src.api.schemas.registrations import REGISTRATION_CREATE_EXAMPLE
from src.core.auth.models import AuthSession
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore


# ===========================================================
# Registration Endpoint Tests
# ===========================================================


def test_registration_create_openapi_example_is_available() -> None:
    """Keep a copy-ready registration example available in Swagger UI."""
    schema = create_app().openapi()
    example = schema["components"]["schemas"]["RegistrationCreateRequest"]["example"]

    assert example == REGISTRATION_CREATE_EXAMPLE


def _valid_adapter_document() -> dict[str, object]:
    """Return a valid adapter metadata document for processing tests."""
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


def _invalid_adapter_document() -> dict[str, object]:
    """Return invalid adapter metadata that can later be corrected."""
    document = _valid_adapter_document()
    document.pop("version")
    return document


def test_create_registration_endpoint_persists_registration(
    tmp_path: Path,
) -> None:
    """Create a registration through the API and persist it in the configured store."""
    database_path = tmp_path / "registry.sqlite3"
    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    store = SQLiteRegistrationStore(database_path)
    app = create_app()
    app.dependency_overrides[get_registration_store] = lambda: store
    app.dependency_overrides[get_optional_auth_session] = lambda: AuthSession(
        github_login="edwinc"
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/registrations",
        json={
            "adapter_name": "Example Adapter",
            "repository_location": str(repository),
            "license_value": "MIT",
            "doi": "10.5281/zenodo.1234567",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["registration_id"]
    assert payload["adapter_name"] == "Example Adapter"
    assert payload["adapter_id"] == "example-adapter"
    assert payload["repository_location"] == str(repository.resolve())
    assert payload["repository_kind"] == "local"
    assert payload["status"] == "SUBMITTED"
    assert payload["license_value"] == "MIT"
    assert payload["doi"] == "10.5281/zenodo.1234567"
    assert payload["submitted_by_github_login"] == "edwinc"

    stored = store.get_registration(payload["registration_id"])
    assert stored is not None
    assert stored.license_value == "MIT"
    assert stored.doi == "10.5281/zenodo.1234567"
    assert stored.submitted_by_github_login == "edwinc"


def test_create_registration_endpoint_maps_missing_repository_to_bad_request(
    tmp_path: Path,
) -> None:
    """Return a client error when the submitted local repository does not exist."""
    database_path = tmp_path / "registry.sqlite3"
    missing_repository = tmp_path / "missing-adapter-repo"
    store = SQLiteRegistrationStore(database_path)
    app = create_app()
    app.dependency_overrides[get_registration_store] = lambda: store
    client = TestClient(app)

    response = client.post(
        "/api/v1/registrations",
        json={
            "adapter_name": "Example Adapter",
            "repository_location": str(missing_repository),
        },
    )

    assert response.status_code == 400
    assert "Repository path not found" in response.json()["detail"]


def test_get_registration_endpoint_returns_stored_registration(
    tmp_path: Path,
) -> None:
    """Return a stored registration by identifier through the API."""
    database_path = tmp_path / "registry.sqlite3"
    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    store = SQLiteRegistrationStore(database_path)
    app = create_app()
    app.dependency_overrides[get_registration_store] = lambda: store
    client = TestClient(app)

    create_response = client.post(
        "/api/v1/registrations",
        json={
            "adapter_name": "Example Adapter",
            "repository_location": str(repository),
            "license_value": "MIT",
            "doi": "10.5281/zenodo.1234567",
        },
    )
    registration_id = create_response.json()["registration_id"]

    response = client.get(f"/api/v1/registrations/{registration_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["registration_id"] == registration_id
    assert payload["adapter_name"] == "Example Adapter"
    assert payload["adapter_id"] == "example-adapter"
    assert payload["repository_location"] == str(repository.resolve())
    assert payload["repository_kind"] == "local"
    assert payload["status"] == "SUBMITTED"
    assert payload["license_value"] == "MIT"
    assert payload["doi"] == "10.5281/zenodo.1234567"
    assert payload["metadata_path"] is None
    assert payload["metadata"] is None
    assert payload["profile_version"] is None
    assert payload["updated_at"] is not None
    assert payload["uniqueness_key"] is None
    assert payload["validation_errors"] is None


def test_get_registration_endpoint_returns_not_found_for_unknown_registration(
    tmp_path: Path,
) -> None:
    """Return 404 when a registration identifier is unknown."""
    database_path = tmp_path / "registry.sqlite3"
    store = SQLiteRegistrationStore(database_path)
    app = create_app()
    app.dependency_overrides[get_registration_store] = lambda: store
    client = TestClient(app)

    response = client.get("/api/v1/registrations/missing-registration")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Registration not found: missing-registration",
    }


def test_list_registrations_endpoint_returns_empty_list(
    tmp_path: Path,
) -> None:
    """Return an empty list when no active registrations exist."""
    database_path = tmp_path / "registry.sqlite3"
    store = SQLiteRegistrationStore(database_path)
    app = create_app()
    app.dependency_overrides[get_registration_store] = lambda: store
    client = TestClient(app)

    response = client.get("/api/v1/registrations")

    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_list_registrations_endpoint_returns_active_registrations(
    tmp_path: Path,
) -> None:
    """Return active registrations in stable creation order."""
    database_path = tmp_path / "registry.sqlite3"
    first_repository = tmp_path / "first-adapter-repo"
    second_repository = tmp_path / "second-adapter-repo"
    first_repository.mkdir()
    second_repository.mkdir()
    store = SQLiteRegistrationStore(database_path)
    app = create_app()
    app.dependency_overrides[get_registration_store] = lambda: store
    client = TestClient(app)

    first_response = client.post(
        "/api/v1/registrations",
        json={
            "adapter_name": "First Adapter",
            "repository_location": str(first_repository),
            "license_value": "MIT",
        },
    )
    second_response = client.post(
        "/api/v1/registrations",
        json={
            "adapter_name": "Second Adapter",
            "repository_location": str(second_repository),
            "license_value": "Apache-2.0",
        },
    )

    response = client.get("/api/v1/registrations")

    assert response.status_code == 200
    payload = response.json()
    assert [item["registration_id"] for item in payload["items"]] == [
        first_response.json()["registration_id"],
        second_response.json()["registration_id"],
    ]
    assert [item["adapter_name"] for item in payload["items"]] == [
        "First Adapter",
        "Second Adapter",
    ]
    assert [item["status"] for item in payload["items"]] == [
        "SUBMITTED",
        "SUBMITTED",
    ]
    assert [item["license_value"] for item in payload["items"]] == [
        "MIT",
        "Apache-2.0",
    ]
    assert all("metadata" not in item for item in payload["items"])
    assert all("metadata_path" not in item for item in payload["items"])
    assert all("validation_errors" not in item for item in payload["items"])


def test_list_registrations_endpoint_omits_processed_metadata(
    tmp_path: Path,
) -> None:
    """Keep list responses compact even after a registration is processed."""
    database_path = tmp_path / "registry.sqlite3"
    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    (repository / "croissant.jsonld").write_text(
        json.dumps(_valid_adapter_document()),
        encoding="utf-8",
    )
    store = SQLiteRegistrationStore(database_path)
    app = create_app()
    app.dependency_overrides[get_registration_store] = lambda: store
    client = TestClient(app)
    create_response = client.post(
        "/api/v1/registrations",
        json={
            "adapter_name": "Example Adapter",
            "repository_location": str(repository),
            "license_value": "MIT",
            "doi": "10.5281/zenodo.1234567",
        },
    )
    registration_id = create_response.json()["registration_id"]
    process_response = client.post(f"/api/v1/registrations/{registration_id}/process")
    assert process_response.status_code == 200
    assert process_response.json()["metadata"]

    response = client.get("/api/v1/registrations")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["registration_id"] == registration_id
    assert item["status"] == "VALID"
    assert item["profile_version"] == "v1"
    assert item["uniqueness_key"] == "example-adapter::1.0.0"
    assert "metadata" not in item
    assert "metadata_path" not in item
    assert "validation_errors" not in item


def test_process_registration_endpoint_marks_registration_valid(
    tmp_path: Path,
) -> None:
    """Process one submitted registration and return the updated detail."""
    database_path = tmp_path / "registry.sqlite3"
    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    (repository / "croissant.jsonld").write_text(
        json.dumps(_valid_adapter_document()),
        encoding="utf-8",
    )
    store = SQLiteRegistrationStore(database_path)
    app = create_app()
    app.dependency_overrides[get_registration_store] = lambda: store
    client = TestClient(app)
    create_response = client.post(
        "/api/v1/registrations",
        json={
            "adapter_name": "Example Adapter",
            "repository_location": str(repository),
            "license_value": "MIT",
            "doi": "10.5281/zenodo.1234567",
        },
    )
    registration_id = create_response.json()["registration_id"]

    response = client.post(f"/api/v1/registrations/{registration_id}/process")

    assert response.status_code == 200
    payload = response.json()
    assert payload["registration_id"] == registration_id
    assert payload["status"] == "VALID"
    assert payload["metadata_path"] == str(repository / "croissant.jsonld")
    assert payload["profile_version"] == "v1"
    assert payload["uniqueness_key"] == "example-adapter::1.0.0"
    assert payload["license_value"] == "MIT"
    assert payload["doi"] == "10.5281/zenodo.1234567"


def test_process_registration_endpoint_returns_not_found_for_unknown_registration(
    tmp_path: Path,
) -> None:
    """Return 404 when processing an unknown registration identifier."""
    database_path = tmp_path / "registry.sqlite3"
    store = SQLiteRegistrationStore(database_path)
    app = create_app()
    app.dependency_overrides[get_registration_store] = lambda: store
    client = TestClient(app)

    response = client.post("/api/v1/registrations/missing-registration/process")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Registration not found: missing-registration",
    }


def test_process_registration_endpoint_maps_processing_failure_to_bad_request(
    tmp_path: Path,
) -> None:
    """Return a client error when processing cannot discover metadata."""
    database_path = tmp_path / "registry.sqlite3"
    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    store = SQLiteRegistrationStore(database_path)
    app = create_app()
    app.dependency_overrides[get_registration_store] = lambda: store
    client = TestClient(app)
    create_response = client.post(
        "/api/v1/registrations",
        json={
            "adapter_name": "Example Adapter",
            "repository_location": str(repository),
        },
    )
    registration_id = create_response.json()["registration_id"]

    response = client.post(f"/api/v1/registrations/{registration_id}/process")

    assert response.status_code == 400
    assert "croissant.jsonld" in response.json()["detail"]


def test_revalidate_registration_endpoint_reprocesses_corrected_invalid_source(
    tmp_path: Path,
) -> None:
    """Revalidate an invalid registration after its metadata is corrected."""
    database_path = tmp_path / "registry.sqlite3"
    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    metadata_path = repository / "croissant.jsonld"
    metadata_path.write_text(
        json.dumps(_invalid_adapter_document()),
        encoding="utf-8",
    )
    store = SQLiteRegistrationStore(database_path)
    app = create_app()
    app.dependency_overrides[get_registration_store] = lambda: store
    client = TestClient(app)
    create_response = client.post(
        "/api/v1/registrations",
        json={
            "adapter_name": "Example Adapter",
            "repository_location": str(repository),
            "license_value": "MIT",
            "doi": "10.5281/zenodo.1234567",
        },
    )
    registration_id = create_response.json()["registration_id"]
    process_response = client.post(f"/api/v1/registrations/{registration_id}/process")
    assert process_response.status_code == 200
    assert process_response.json()["status"] == "INVALID"

    metadata_path.write_text(
        json.dumps(_valid_adapter_document()),
        encoding="utf-8",
    )

    response = client.post(f"/api/v1/registrations/{registration_id}/revalidate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["registration_id"] == registration_id
    assert payload["status"] == "VALID"
    assert payload["metadata_path"] == str(metadata_path)
    assert payload["profile_version"] == "v1"
    assert payload["uniqueness_key"] == "example-adapter::1.0.0"
    assert payload["validation_errors"] is None
    assert payload["license_value"] == "MIT"
    assert payload["doi"] == "10.5281/zenodo.1234567"


def test_revalidate_registration_endpoint_returns_not_found_for_unknown_registration(
    tmp_path: Path,
) -> None:
    """Return 404 when revalidating an unknown registration identifier."""
    database_path = tmp_path / "registry.sqlite3"
    store = SQLiteRegistrationStore(database_path)
    app = create_app()
    app.dependency_overrides[get_registration_store] = lambda: store
    client = TestClient(app)

    response = client.post("/api/v1/registrations/missing-registration/revalidate")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Registration not found: missing-registration",
    }


def test_revalidate_registration_endpoint_rejects_submitted_registration(
    tmp_path: Path,
) -> None:
    """Return 400 when a registration is not eligible for on-demand revalidation."""
    database_path = tmp_path / "registry.sqlite3"
    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    store = SQLiteRegistrationStore(database_path)
    app = create_app()
    app.dependency_overrides[get_registration_store] = lambda: store
    client = TestClient(app)
    create_response = client.post(
        "/api/v1/registrations",
        json={
            "adapter_name": "Example Adapter",
            "repository_location": str(repository),
        },
    )
    registration_id = create_response.json()["registration_id"]

    response = client.post(f"/api/v1/registrations/{registration_id}/revalidate")

    assert response.status_code == 400
    assert response.json() == {
        "detail": (
            "On-demand revalidation is only available for INVALID or FETCH_FAILED "
            "registrations."
        ),
    }


def test_list_registration_events_endpoint_returns_fetch_failed_event(
    tmp_path: Path,
) -> None:
    """Expose FETCH_FAILED through the registration event history endpoint."""
    database_path = tmp_path / "registry.sqlite3"
    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    metadata_path = repository / "croissant.jsonld"
    metadata_path.write_text(
        json.dumps(_invalid_adapter_document()),
        encoding="utf-8",
    )
    store = SQLiteRegistrationStore(database_path)
    app = create_app()
    app.dependency_overrides[get_registration_store] = lambda: store
    client = TestClient(app)
    create_response = client.post(
        "/api/v1/registrations",
        json={
            "adapter_name": "Example Adapter",
            "repository_location": str(repository),
            "license_value": "MIT",
            "doi": "10.5281/zenodo.1234567",
        },
    )
    registration_id = create_response.json()["registration_id"]
    process_response = client.post(f"/api/v1/registrations/{registration_id}/process")
    assert process_response.status_code == 200
    assert process_response.json()["status"] == "INVALID"
    metadata_path.unlink()

    revalidate_response = client.post(
        f"/api/v1/registrations/{registration_id}/revalidate"
    )
    assert revalidate_response.status_code == 400

    response = client.get(f"/api/v1/registrations/{registration_id}/events")

    assert response.status_code == 200
    payload = response.json()
    event_types = [item["event_type"] for item in payload["items"]]
    assert event_types == [
        "SUBMITTED",
        "INVALID_SCHEMA",
        "REVALIDATED",
        "FETCH_FAILED",
    ]
    fetch_failed_event = payload["items"][-1]
    assert fetch_failed_event["source_id"] == registration_id
    assert fetch_failed_event["message"] == "Registration fetch/discovery failed."
    assert fetch_failed_event["error_details"]
    assert "croissant.jsonld" in fetch_failed_event["error_details"][0]


def test_list_registration_events_endpoint_returns_not_found_for_unknown_registration(
    tmp_path: Path,
) -> None:
    """Return 404 when event history is requested for an unknown registration."""
    database_path = tmp_path / "registry.sqlite3"
    store = SQLiteRegistrationStore(database_path)
    app = create_app()
    app.dependency_overrides[get_registration_store] = lambda: store
    client = TestClient(app)

    response = client.get("/api/v1/registrations/missing-registration/events")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Registration not found: missing-registration",
    }
