from __future__ import annotations

from pathlib import Path

from src.persistence.registration_sqlite_store import SQLiteRegistrationStore
from tests.unit.api.adapter_test_helpers import (
    create_adapter_client,
    create_adapter_entry,
)


def test_latest_adapter_uses_github_repository_owner_avatar(tmp_path: Path) -> None:
    """
    Use the GitHub repository owner avatar at response time.
    """
    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    create_adapter_entry(
        store,
        None,
        adapter_id="example-adapter",
        adapter_name="Example Adapter",
        repository_location="https://github.com/biocypher/example",
        submitted_by_github_login="submitter",
    )
    payload = create_adapter_client(store).get("/api/v1/adapters/latest").json()
    maintainer = payload["items"][0]["maintainers"][0]

    assert maintainer["username"] == "biocypher"
    assert maintainer["avatar_url"] == "https://github.com/biocypher.png"
    assert maintainer["profile_url"] == "https://github.com/biocypher"


def test_latest_adapter_uses_gitlab_repository_owner(
    tmp_path: Path,
) -> None:
    """
    Use the GitLab repository owner without a public API lookup.
    """
    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    create_adapter_entry(
        store,
        None,
        adapter_id="example-adapter",
        adapter_name="Example Adapter",
        repository_location="https://gitlab.example.org/alice/example",
    )
    payload = create_adapter_client(store).get("/api/v1/adapters/latest").json()
    maintainer = payload["items"][0]["maintainers"][0]

    assert maintainer["username"] == "alice"
    assert maintainer["avatar_url"] is None
    assert maintainer["profile_url"] == "https://gitlab.example.org/alice"


def test_latest_adapter_uses_self_hosted_repository_owner(
    tmp_path: Path,
) -> None:
    """
    Keep maintainer display data for self-hosted repository URLs.
    """
    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    create_adapter_entry(
        store,
        None,
        adapter_id="example-adapter",
        adapter_name="Example Adapter",
        repository_location="https://institution.example.org/team/example",
    )
    payload = create_adapter_client(store).get("/api/v1/adapters/latest").json()
    item = payload["items"][0]
    maintainer = item["maintainers"][0]

    assert item["repository_location"] == "https://institution.example.org/team/example"
    assert maintainer["username"] == "team"
    assert maintainer["avatar_url"] is None
    assert item["adapter_id"] == "example-adapter"
