from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import update

from src.persistence.registration_sqlite_store import SQLiteRegistrationStore
from src.persistence.tables import registry_entries_table
from tests.support.registration_fixtures import accepted_source
from tests.unit.api.adapter_test_helpers import create_adapter_client


@pytest.fixture
def search_store(tmp_path: Path) -> SQLiteRegistrationStore:
    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    adapter_metadata: list[tuple[str, str, object, bool]] = [
        ("pathway", "Pathway Adapter", ["Cell Signaling", "pathways"], True),
        ("expression", "Expression Adapter", "cell signaling,expression", True),
        ("literal", "50%_ Adapter", None, True),
        ("legacy", "Legacy Adapter", {"topic": "hidden"}, True),
        ("retired", "Retired Adapter", ["Cell Signaling", "hidden"], False),
    ]
    for position, (adapter_id, adapter_name, keywords, is_active) in enumerate(
        adapter_metadata, start=1
    ):
        registration = accepted_source(
            store,
            f"https://github.com/example/{adapter_id}",
            metadata={
                "@id": adapter_id,
                "name": adapter_name,
                "version": "1.0.0",
                "keywords": keywords,
            },
        )
        with store.engine.begin() as connection:
            connection.execute(
                update(registry_entries_table)
                .where(
                    registry_entries_table.c.source_id == registration.registration_id
                )
                .values(
                    created_at="2026-11-01T12:00:00+00:00",
                    updated_at=f"2026-11-{position:02d}T12:00:00+00:00",
                    is_active=is_active,
                )
            )
    return store


@pytest.mark.parametrize(
    ("query", "adapter_ids"),
    [
        ("cell signaling", ["expression", "pathway"]),
        (" CELL\tSIGNALING\n", ["expression", "pathway"]),
        ("cElLsIgNaLiNg", ["expression", "pathway"]),
        ("signaling", ["expression", "pathway"]),
        ("p a t h w a y", ["pathway"]),
        ("expression", ["expression"]),
        ("%_", ["literal"]),
        ("hidden", []),
        ("retired", []),
        ("unknown", []),
    ],
)
def test_search_adapters_matches_titles_and_keywords(
    search_store: SQLiteRegistrationStore, query: str, adapter_ids: list[str]
) -> None:
    response = create_adapter_client(search_store).get(
        "/api/v1/adapters/search", params={"query": query}
    )
    assert response.status_code == 200
    assert [item["adapter_id"] for item in response.json()["items"]] == adapter_ids
    assert all("metadata" not in item for item in response.json()["items"])


@pytest.mark.parametrize("limit", [1, 2, 10_000])
def test_search_store_limits_newest_matches_without_changing_entries(
    search_store: SQLiteRegistrationStore, limit: int
) -> None:
    original_entries = search_store.list_registry_entries()
    matches = search_store.search_registry_entries_by_adapter_name("signaling", limit)
    expected_names = ["Expression Adapter", "Pathway Adapter"][:limit]
    assert [entry.adapter_name for entry in matches] == expected_names
    assert (matches[0].metadata or {})["keywords"] == "cell signaling,expression"
    assert search_store.list_registry_entries() == original_entries
