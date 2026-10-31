"""Published registry listings, filtering, and operator refresh contracts."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.dependencies import get_registration_store
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore
from tests.support.registration_fixtures import accepted_source, historical_source


@pytest.fixture
def store(tmp_path):
    return SQLiteRegistrationStore(tmp_path / "registry.sqlite3")


@pytest.fixture
def client(store):
    app = create_app()
    app.dependency_overrides[get_registration_store] = lambda: store
    return TestClient(app)


@pytest.mark.parametrize("path", ["registrations", "entries"])
def test_registry_lists_empty(client, path):
    response = client.get(f"/api/v1/registry/{path}")
    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_registration_list_contains_published_source_latest_attempt_without_status(
    client, store
):
    published = accepted_source(store, "https://github.com/owner/published")
    historical_source(store, "https://github.com/owner/legacy")
    store.record_update_failure(
        published.registration_id,
        "INVALID_SCHEMA",
        ["Missing license"],
        "Metadata rejected",
        datetime.now(UTC),
    )
    response = client.get("/api/v1/registry/registrations")
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    row = response.json()["items"][0]
    assert row["registration_id"] == published.registration_id
    assert row["latest_event_type"] == "INVALID_SCHEMA"
    assert "status" not in row
    assert row["published_version"] == "1.0.0"


def test_registration_list_filters_latest_event(client, store):
    first = accepted_source(store, "https://github.com/owner/first")
    accepted_source(
        store,
        "https://github.com/owner/second",
        metadata={"@id": "second", "name": "Second", "version": "1.0.0"},
    )
    store.record_update_failure(
        first.registration_id,
        "INVALID_SCHEMA",
        ["Missing license"],
        "Metadata rejected",
        datetime.now(UTC),
    )
    response = client.get(
        "/api/v1/registry/registrations", params={"latest_event": "INVALID_SCHEMA"}
    )
    assert [item["registration_id"] for item in response.json()["items"]] == [
        first.registration_id
    ]
    assert (
        client.get(
            "/api/v1/registry/registrations", params={"latest_event": "unknown"}
        ).status_code
        == 422
    )
    parameters = client.app.openapi()["paths"]["/api/v1/registry/registrations"][
        "get"
    ].get("parameters", [])
    assert "status" not in [item["name"] for item in parameters]


def test_entries_return_canonical_metadata_light_rows(client, store):
    source = accepted_source(store, "https://github.com/owner/repo")
    response = client.get("/api/v1/registry/entries")
    assert response.status_code == 200
    row = response.json()["items"][0]
    assert row["source_id"] == source.registration_id
    assert row["adapter_version"] == "1.0.0"
    assert "metadata" not in row
    detail = client.get(f"/api/v1/registry/entries/{row['entry_id']}")
    assert detail.status_code == 200 and detail.json() == row
    assert client.get("/api/v1/registry/entries/missing").status_code == 404


def test_unpublished_sources_have_no_registry_entries(client, store):
    historical_source(store, "https://github.com/owner/legacy")
    assert client.get("/api/v1/registry/entries").json() == {"items": []}


def test_cli_refresh_summary_remains_readable_in_api(client, store):
    from src.core.registration.models import BatchRefreshSummary

    store.record_batch_refresh(
        BatchRefreshSummary(active_sources=1, processed=1, unchanged=1),
        datetime.now(UTC),
        datetime.now(UTC),
    )
    response = client.get("/api/v1/registry/refreshes/latest")
    assert response.status_code == 200
    assert response.json()["unchanged"] == 1


@pytest.mark.parametrize("signed_in", [False, True])
def test_global_refresh_cannot_be_triggered_through_api(client, store, signed_in):
    from src.api.dependencies import get_optional_auth_session
    from src.core.auth.models import AuthSession

    client.app.dependency_overrides[get_optional_auth_session] = lambda: (
        AuthSession("123") if signed_in else None
    )
    response = client.post("/api/v1/registry/refreshes")
    assert response.status_code == 404
    assert store.get_latest_batch_refresh() is None
    assert "/api/v1/registry/refreshes" not in client.app.openapi()["paths"]
