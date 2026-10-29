"""HTTP contracts for synchronous registration and automatic pre-flight."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from src.api.app import create_app
from src.api.dependencies import get_optional_auth_session, get_registration_store
from src.api.schemas.registrations import REGISTRATION_CREATE_EXAMPLE
from src.core.auth.models import AuthSession
from src.core.registration.service import submit_registration
from src.core.shared.errors import RepositoryUnavailableError
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore
from src.persistence.tables import (
    registration_events_table,
    registration_sources_table,
    registry_entries_table,
)
from tests.support.croissant_fixtures import sample_adapter_document


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    path = tmp_path / "adapter"
    path.mkdir()
    (path / "croissant.jsonld").write_text(json.dumps(sample_adapter_document()))
    return path


@pytest.fixture
def store(tmp_path: Path) -> SQLiteRegistrationStore:
    return SQLiteRegistrationStore(tmp_path / "registry.sqlite3")


@pytest.fixture
def client(store) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_registration_store] = lambda: store
    app.dependency_overrides[get_optional_auth_session] = lambda: AuthSession(
        github_user_id="12345"
    )
    return TestClient(app)


def assert_no_registration_writes(store):
    with store.engine.connect() as connection:
        for table in (
            registration_sources_table,
            registry_entries_table,
            registration_events_table,
        ):
            assert connection.scalar(select(func.count()).select_from(table)) == 0


def test_registration_create_openapi_example_is_available():
    schema = create_app().openapi()
    assert (
        schema["components"]["schemas"]["RegistrationCreateRequest"]["example"]
        == REGISTRATION_CREATE_EXAMPLE
    )


def test_create_registration_endpoint_persists_accepted_registration(
    client, repository, store
):
    response = client.post(
        "/api/v1/registrations",
        json={
            "repository_location": str(repository),
            "license_value": "MIT",
            "doi": "10.5281/zenodo.1234567",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["attempt_status"] == "SUCCEEDED"
    assert payload["adapter_name"] == "Example Adapter"
    assert payload["adapter_id"] == "example-adapter"
    assert payload["published_version"] == "1.0.0"
    stored = store.get_registration(payload["registration_id"])
    assert stored.status == "VALID"
    assert stored.license_value == "MIT"
    assert stored.doi == "10.5281/zenodo.1234567"
    assert stored.submitted_by_github_user_id == "12345"
    assert [
        event.event_type
        for event in store.list_registration_events(stored.registration_id)
    ] == ["VALID_CREATED"]


@pytest.mark.parametrize(
    "content, reason",
    [
        ("{", "INVALID_JSON"),
        ("[]", "INVALID_JSON"),
        ("{}", "SCHEMA_INVALID"),
        (None, "METADATA_NOT_FOUND"),
    ],
)
def test_failed_first_registration_returns_errors_without_records(
    client, repository, store, content, reason
):
    path = repository / "croissant.jsonld"
    if content is None:
        path.unlink()
    else:
        path.write_text(content)
    response = client.post(
        "/api/v1/registrations", json={"repository_location": str(repository)}
    )
    assert response.status_code == 200
    assert response.json()["attempt_status"] == "FAILED"
    assert response.json()["reason_code"] == reason
    assert response.json()["registration_id"] is None
    assert response.json()["published_version"] is None
    assert_no_registration_writes(store)


def test_retry_repeats_initial_request_with_same_version(client, repository, store):
    path = repository / "croissant.jsonld"
    path.write_text("{")
    assert (
        client.post(
            "/api/v1/registrations", json={"repository_location": str(repository)}
        ).json()["attempt_status"]
        == "FAILED"
    )
    assert_no_registration_writes(store)
    path.write_text(json.dumps(sample_adapter_document()))
    response = client.post(
        "/api/v1/registrations", json={"repository_location": str(repository)}
    )
    assert response.status_code == 201
    assert response.json()["published_version"] == "1.0.0"


def test_duplicate_repository_returns_conflict(client, repository, store):
    first = client.post(
        "/api/v1/registrations", json={"repository_location": str(repository)}
    ).json()
    response = client.post(
        "/api/v1/registrations", json={"repository_location": str(repository)}
    )
    assert response.status_code == 409
    assert "already registered" in response.json()["detail"]
    assert len(store.list_registration_events(first["registration_id"])) == 1


def test_missing_local_path_is_a_request_error(client, tmp_path, store):
    response = client.post(
        "/api/v1/registrations", json={"repository_location": str(tmp_path / "absent")}
    )
    assert response.status_code == 400
    assert_no_registration_writes(store)


def test_detail_and_list_expose_accepted_registration(client, repository):
    created = client.post(
        "/api/v1/registrations", json={"repository_location": str(repository)}
    ).json()
    detail = client.get(f"/api/v1/registrations/{created['registration_id']}").json()
    assert detail["status"] == "VALID"
    assert detail["metadata"]["version"] == "1.0.0"
    items = client.get("/api/v1/registrations").json()["items"]
    assert len(items) == 1
    assert items[0]["status"] == "VALID"
    assert "metadata" not in items[0]
    assert "validation_errors" not in items[0]


def test_empty_registration_list(client):
    assert client.get("/api/v1/registrations").json() == {"items": []}


@pytest.mark.parametrize(
    "suffix, method",
    [("", "get"), ("/events", "get"), ("/process", "post"), ("/revalidate", "post")],
)
def test_unknown_registration_returns_not_found(client, suffix, method):
    assert (
        getattr(client, method)(f"/api/v1/registrations/missing{suffix}").status_code
        == 404
    )


@pytest.mark.parametrize("present, expected", [(True, "FOUND"), (False, "NOT_FOUND")])
def test_presence_check_normalizes_branch_links(monkeypatch, present, expected):
    exists = Mock(return_value=present)
    monkeypatch.setattr("src.api.routers.registrations.remote_metadata_exists", exists)
    response = TestClient(create_app()).get(
        "/api/v1/registrations/croissant-file-present-check",
        params={
            "repository_url": "https://gitlab.example.org/group/subgroup/repo/-/blob/develop/croissant.jsonld",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == expected
    assert response.json()["has_croissant_file"] is present
    exists.assert_called_once_with("https://gitlab.example.org/group/subgroup/repo")


def test_inaccessible_repository_is_unavailable_not_missing(monkeypatch):
    monkeypatch.setattr(
        "src.api.routers.registrations.remote_metadata_exists",
        Mock(side_effect=RepositoryUnavailableError("Access restricted.")),
    )
    response = TestClient(create_app()).get(
        "/api/v1/registrations/croissant-file-present-check",
        params={"repository_url": "https://github.com/org/repo"},
    )
    assert response.json()["status"] == "UNAVAILABLE"
    assert response.json()["reason_code"] == "REPOSITORY_UNAVAILABLE"


def test_invalid_presence_url_is_unavailable():
    response = TestClient(create_app()).get(
        "/api/v1/registrations/croissant-file-present-check",
        params={"repository_url": "not-a-url"},
    )
    assert response.json()["status"] == "UNAVAILABLE"
    assert response.json()["reason_code"] == "INVALID_REPOSITORY_URL"


def test_legacy_process_endpoint_can_process_staged_sources(client, repository, store):
    staged = submit_registration(str(repository), store)
    response = client.post(f"/api/v1/registrations/{staged.registration_id}/process")
    assert response.status_code == 200
    assert response.json()["status"] == "VALID"


def test_legacy_processing_cannot_bypass_update_ownership(client, repository, store):
    staged = submit_registration(
        str(repository), store, submitted_by_github_user_id="another-account"
    )
    for action in ("process", "revalidate"):
        response = client.post(
            f"/api/v1/registrations/{staged.registration_id}/{action}"
        )
        assert response.status_code == 403
    assert [
        event.event_type
        for event in store.list_registration_events(staged.registration_id)
    ] == ["SUBMITTED"]


def test_success_event_is_available_from_history(client, repository):
    created = client.post(
        "/api/v1/registrations", json={"repository_location": str(repository)}
    ).json()
    events = client.get(
        f"/api/v1/registrations/{created['registration_id']}/events"
    ).json()["items"]
    assert [event["event_type"] for event in events] == ["VALID_CREATED"]


def test_registration_openapi_documents_success_and_unsuccessful_attempts():
    responses = create_app().openapi()["paths"]["/api/v1/registrations"]["post"][
        "responses"
    ]
    assert "200" in responses and "201" in responses and "409" in responses
    assert (
        responses["200"]["content"]["application/json"]["schema"]
        == responses["201"]["content"]["application/json"]["schema"]
    )
