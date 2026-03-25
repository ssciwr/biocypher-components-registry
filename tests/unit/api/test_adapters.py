from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.dependencies import get_registration_store
from src.core.registration.service import submit_registration
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore


# ===========================================================
# Adapter Catalog Endpoint Tests
# ===========================================================


def _create_adapter_entry(
    store: SQLiteRegistrationStore,
    repository: Path,
    *,
    adapter_id: str,
    adapter_name: str,
    version: str,
) -> None:
    """Create one canonical registry entry for adapter catalog tests."""
    repository.mkdir()
    registration = submit_registration(adapter_name, str(repository), store)
    store.mark_registration_valid(
        registration_id=registration.registration_id,
        metadata={"@id": adapter_id, "name": adapter_name, "version": version},
        metadata_path=str(repository / "croissant.jsonld"),
        profile_version="v1",
        uniqueness_key=f"{adapter_id}::{version}",
        observed_checksum=f"checksum-{adapter_id}-{version}",
    )


def _create_adapter_client(
    store: SQLiteRegistrationStore,
) -> TestClient:
    """Create an API test client with an overridden registration store."""
    app = create_app()
    app.dependency_overrides[get_registration_store] = lambda: store
    return TestClient(app)


def test_list_adapters_endpoint_returns_empty_catalog(tmp_path: Path) -> None:
    """Return an empty adapter catalog when no canonical entries exist."""
    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    client = _create_adapter_client(store)

    response = client.get("/api/v1/adapters")

    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_list_adapters_endpoint_groups_canonical_versions(
    tmp_path: Path,
) -> None:
    """Return one public catalog item per canonical adapter identifier."""
    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    _create_adapter_entry(
        store,
        tmp_path / "adapter-v1",
        adapter_id="example-adapter",
        adapter_name="Example Adapter",
        version="1.0.0",
    )
    _create_adapter_entry(
        store,
        tmp_path / "adapter-v2",
        adapter_id="example-adapter",
        adapter_name="Example Adapter",
        version="2.0.0",
    )
    _create_adapter_entry(
        store,
        tmp_path / "other-adapter",
        adapter_id="other-adapter",
        adapter_name="Other Adapter",
        version="1.0.0",
    )
    client = _create_adapter_client(store)

    response = client.get("/api/v1/adapters")

    assert response.status_code == 200
    payload = response.json()
    assert [item["adapter_id"] for item in payload["items"]] == [
        "example-adapter",
        "other-adapter",
    ]
    assert payload["items"][0]["latest_version"] == "2.0.0"
    assert payload["items"][0]["version_count"] == 2
    assert "metadata" not in payload["items"][0]


def test_get_adapter_endpoint_returns_versions_without_metadata(
    tmp_path: Path,
) -> None:
    """Return one adapter with its canonical versions."""
    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    _create_adapter_entry(
        store,
        tmp_path / "adapter-v1",
        adapter_id="example-adapter",
        adapter_name="Example Adapter",
        version="1.0.0",
    )
    _create_adapter_entry(
        store,
        tmp_path / "adapter-v2",
        adapter_id="example-adapter",
        adapter_name="Example Adapter",
        version="2.0.0",
    )
    client = _create_adapter_client(store)

    response = client.get("/api/v1/adapters/example-adapter")

    assert response.status_code == 200
    payload = response.json()
    assert payload["adapter_id"] == "example-adapter"
    assert payload["adapter_name"] == "Example Adapter"
    assert payload["latest_version"] == "2.0.0"
    assert [version["adapter_version"] for version in payload["versions"]] == [
        "1.0.0",
        "2.0.0",
    ]
    assert payload["versions"][0]["registry_entry_id"]
    assert payload["versions"][0]["profile_version"] == "v1"
    assert "metadata" not in payload["versions"][0]


def test_get_adapter_version_metadata_endpoint_returns_full_metadata(
    tmp_path: Path,
) -> None:
    """Return full Croissant metadata for one public adapter version."""
    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    _create_adapter_entry(
        store,
        tmp_path / "adapter-v1",
        adapter_id="example-adapter",
        adapter_name="Example Adapter",
        version="1.0.0",
    )
    client = _create_adapter_client(store)

    response = client.get("/api/v1/adapters/example-adapter/versions/1.0.0/metadata")

    assert response.status_code == 200
    payload = response.json()
    assert payload["adapter_id"] == "example-adapter"
    assert payload["adapter_version"] == "1.0.0"
    assert payload["registry_entry_id"]
    assert payload["metadata"] == {
        "@id": "example-adapter",
        "name": "Example Adapter",
        "version": "1.0.0",
    }


def test_get_adapter_version_metadata_endpoint_returns_not_found_for_unknown_version(
    tmp_path: Path,
) -> None:
    """Return 404 when the adapter exists but the requested version does not."""
    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    _create_adapter_entry(
        store,
        tmp_path / "adapter-v1",
        adapter_id="example-adapter",
        adapter_name="Example Adapter",
        version="1.0.0",
    )
    client = _create_adapter_client(store)

    response = client.get("/api/v1/adapters/example-adapter/versions/2.0.0/metadata")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Adapter version not found: example-adapter 2.0.0",
    }


def test_get_adapter_endpoint_returns_not_found_for_unknown_adapter(
    tmp_path: Path,
) -> None:
    """Return 404 when a public adapter identifier is unknown."""
    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    client = _create_adapter_client(store)

    response = client.get("/api/v1/adapters/missing-adapter")

    assert response.status_code == 404
    assert response.json() == {"detail": "Adapter not found: missing-adapter"}
