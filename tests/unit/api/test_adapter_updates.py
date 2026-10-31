"""Manual update permissions, publication, and persistent summary contracts."""

from __future__ import annotations

import json

import pytest

from src.core.auth.models import AuthSession
from src.core.registration.service import register_adapter
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore
from tests.support.croissant_fixtures import sample_adapter_document
from tests.unit.api.adapter_test_helpers import create_adapter_client


@pytest.fixture
def published_adapter(tmp_path):
    repository = tmp_path / "adapter"
    repository.mkdir()
    (repository / "croissant.jsonld").write_text(json.dumps(sample_adapter_document()))
    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    outcome = register_adapter(
        str(repository), store, actor=AuthSession(github_user_id="owner")
    )
    return repository, store, outcome.registration


def test_update_uses_delete_ownership_and_unchanged_is_success(published_adapter):
    _, store, registration = published_adapter
    client = create_adapter_client(store, "owner")
    detail = client.get("/api/v1/adapters/example-adapter").json()
    assert detail["can_update"] is True
    assert detail["can_delete"] is True
    response = client.post("/api/v1/adapters/example-adapter/update")
    assert response.status_code == 200
    assert response.json()["attempt_status"] == "SUCCEEDED"
    assert response.json()["message"] == "No changes found."
    assert response.json()["update_applied"] is False
    assert len(store.list_registration_events(registration.registration_id)) == 2


def test_failed_update_summary_survives_reload_and_same_action_retries(
    published_adapter,
):
    repository, store, _ = published_adapter
    client = create_adapter_client(store, "owner")
    metadata = sample_adapter_document()
    metadata["version"] = "1.1.0"
    metadata.pop("license")
    path = repository / "croissant.jsonld"
    path.write_text(json.dumps(metadata))
    response = client.post("/api/v1/adapters/example-adapter/update")
    assert response.json()["attempt_status"] == "FAILED"
    detail = client.get("/api/v1/adapters/example-adapter").json()
    assert detail["version"] == "1.0.0"
    assert detail["latest_attempt"]["attempt_status"] == "FAILED"
    assert detail["latest_attempt"]["published_version"] == "1.0.0"
    assert "Previous metadata retained" in detail["latest_attempt"]["message"]
    metadata["license"] = sample_adapter_document()["license"]
    path.write_text(json.dumps(metadata))
    response = client.post("/api/v1/adapters/example-adapter/update")
    assert response.json()["attempt_status"] == "SUCCEEDED"
    assert response.json()["update_applied"] is True
    detail = client.get("/api/v1/adapters/example-adapter").json()
    assert detail["version"] == "1.1.0"
    assert detail["latest_attempt"]["message"] == "Updated from 1.0.0 to 1.1.0."


@pytest.mark.parametrize("account, status", [(None, 401), ("other", 403)])
def test_update_rejects_unsigned_or_different_accounts(
    published_adapter, account, status
):
    _, store, registration = published_adapter
    client = create_adapter_client(store, account)
    detail = client.get("/api/v1/adapters/example-adapter").json()
    assert detail["can_update"] is False
    assert client.post("/api/v1/adapters/example-adapter/update").status_code == status
    assert len(store.list_registration_events(registration.registration_id)) == 1


def test_unknown_adapter_update_returns_not_found(published_adapter):
    _, store, _ = published_adapter
    assert (
        create_adapter_client(store, "owner")
        .post("/api/v1/adapters/absent/update")
        .status_code
        == 404
    )


@pytest.mark.parametrize("field,value", [("@id", None), ("@context", [])])
def test_malformed_jsonld_update_returns_failed_attempt_not_internal_error(
    published_adapter, field, value
):
    repository, store, registration = published_adapter
    document = sample_adapter_document()
    document[field] = value
    document["version"] = "next"
    (repository / "croissant.jsonld").write_text(json.dumps(document))
    response = create_adapter_client(store, github_user_id="owner").post(
        "/api/v1/adapters/example-adapter/update"
    )
    assert response.status_code == 200
    assert response.json()["attempt_status"] == "FAILED"
    assert response.json()["published_version"] == "1.0.0"
    assert len(store.list_registration_events(registration.registration_id)) == 2
