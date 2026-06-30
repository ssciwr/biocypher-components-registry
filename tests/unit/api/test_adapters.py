from __future__ import annotations

from pathlib import Path

from src.persistence.registration_sqlite_store import SQLiteRegistrationStore
from tests.unit.api.adapter_test_helpers import (
    create_adapter_client,
    create_adapter_entry,
)


def test_list_adapters_endpoint_returns_empty_catalog(tmp_path: Path) -> None:
    """Return an empty adapter catalog when no canonical entries exist."""
    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    client = create_adapter_client(store)

    response = client.get("/api/v1/adapters")

    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_list_adapters_endpoint_returns_canonical_adapters(
    tmp_path: Path,
) -> None:
    """Return one public catalog item per canonical adapter identifier."""
    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    create_adapter_entry(
        store,
        tmp_path / "example-adapter",
        adapter_id="example-adapter",
        adapter_name="Example Adapter",
    )
    create_adapter_entry(
        store,
        tmp_path / "other-adapter",
        adapter_id="other-adapter",
        adapter_name="Other Adapter",
    )
    client = create_adapter_client(store)

    response = client.get("/api/v1/adapters")

    assert response.status_code == 200
    payload = response.json()
    assert [item["adapter_id"] for item in payload["items"]] == [
        "example-adapter",
        "other-adapter",
    ]
    assert payload["items"][0]["adapter_name"] == "Example Adapter"
    assert "metadata" not in payload["items"][0]


def test_get_adapter_endpoint_returns_adapter_without_metadata(
    tmp_path: Path,
) -> None:
    """Return one adapter without embedding full Croissant metadata."""
    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    create_adapter_entry(
        store,
        tmp_path / "adapter",
        adapter_id="example-adapter",
        adapter_name="Example Adapter",
        doi="10.1038/nature11416",
        cff_url="https://example.org/CITATION.cff",
    )
    client = create_adapter_client(store)

    response = client.get("/api/v1/adapters/example-adapter")

    assert response.status_code == 200
    payload = response.json()
    assert payload["adapter_id"] == "example-adapter"
    assert payload["adapter_name"] == "Example Adapter"
    assert payload["doi"] == "10.1038/nature11416"
    assert payload["cff_url"] == "https://example.org/CITATION.cff"
    assert "metadata" not in payload


def test_get_adapter_metadata_endpoint_returns_full_metadata(
    tmp_path: Path,
) -> None:
    """Return full Croissant metadata for one public adapter."""
    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    create_adapter_entry(
        store,
        tmp_path / "adapter",
        adapter_id="example-adapter",
        adapter_name="Example Adapter",
    )
    client = create_adapter_client(store)

    response = client.get("/api/v1/adapters/example-adapter/metadata")

    assert response.status_code == 200
    payload = response.json()
    assert payload["adapter_id"] == "example-adapter"
    assert payload["registry_entry_id"]
    assert payload["metadata"] == {
        "@id": "example-adapter",
        "name": "Example Adapter",
    }


def test_get_adapter_metadata_endpoint_returns_not_found_for_unknown_adapter(
    tmp_path: Path,
) -> None:
    """Return 404 when the requested adapter does not exist."""
    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    create_adapter_entry(
        store,
        tmp_path / "adapter",
        adapter_id="example-adapter",
        adapter_name="Example Adapter",
    )
    client = create_adapter_client(store)

    response = client.get("/api/v1/adapters/missing-adapter/metadata")

    assert response.status_code == 404
    assert response.json() == {"detail": "Adapter not found: missing-adapter"}


def test_get_adapter_endpoint_returns_not_found_for_unknown_adapter(
    tmp_path: Path,
) -> None:
    """Return 404 when a public adapter identifier is unknown."""
    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    client = create_adapter_client(store)

    response = client.get("/api/v1/adapters/missing-adapter")

    assert response.status_code == 404
    assert response.json() == {"detail": "Adapter not found: missing-adapter"}
