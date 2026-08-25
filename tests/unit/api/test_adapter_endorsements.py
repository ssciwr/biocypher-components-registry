from __future__ import annotations

from pathlib import Path

from src.persistence.registration_sqlite_store import SQLiteRegistrationStore
from tests.unit.api.adapter_test_helpers import (
    create_adapter_client,
    create_adapter_entry,
)

"""
The production code behind these I manually wrote or drafted over with AI, the tests here are however AI-written based on
other API tests and follow the same structure. As is the adapter helper utility file which allows `create_adapter_entry`.
Feel free to update or change how these tests work, they are for the new endorsement functionality that came out of
the workshop feedback for what users want from the registry.
"""


def test_post_adapter_endorsement_records_single_github_user(tmp_path: Path) -> None:
    """AI-Generated.

    Record one signed-in user's adapter endorsement.
    """
    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    create_adapter_entry(
        store,
        tmp_path / "adapter-v1",
        adapter_id="example-adapter",
        adapter_name="Example Adapter",
    )
    client = create_adapter_client(store, github_user_id="12345")
    first = client.post("/api/v1/adapters/example-adapter/endorse")
    second = client.post("/api/v1/adapters/example-adapter/endorse")
    detail = client.get("/api/v1/adapters/example-adapter").json()

    assert first.status_code == 200
    assert second.json()["endorsement_count"] == 1
    assert detail["endorsed_by_current_user"] is True


def test_post_adapter_endorsement_requires_github_session(tmp_path: Path) -> None:
    """AI-Generated.

    Reject endorsements without a signed-in GitHub account.
    """
    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    create_adapter_entry(
        store,
        tmp_path / "adapter-v1",
        adapter_id="example-adapter",
        adapter_name="Example Adapter",
    )
    response = create_adapter_client(store).post(
        "/api/v1/adapters/example-adapter/endorse"
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "GitHub sign-in required."
    assert store.count_adapter_endorsements("example-adapter") == 0
