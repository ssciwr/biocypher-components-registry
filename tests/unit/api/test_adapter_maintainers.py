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
    item = payload["items"][0]
    maintainer = item["maintainer"]

    assert "maintainers" not in item
    assert maintainer["username"] == "biocypher"
    assert maintainer["avatar_url"] == "https://github.com/biocypher.png"
    assert maintainer["profile_url"] == "https://github.com/biocypher"


def test_latest_adapter_uses_gitlab_repository_owner(
    tmp_path: Path,
) -> None:
    """
    Use the GitLab repository owner avatar endpoint for a real public project.
    """
    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    create_adapter_entry(
        store,
        None,
        adapter_id="example-adapter",
        adapter_name="Example Adapter",
        repository_location="https://gitlab.com/gitlab-org/gitlab",
    )
    payload = create_adapter_client(store).get("/api/v1/adapters/latest").json()
    item = payload["items"][0]
    maintainer = item["maintainer"]

    assert "maintainers" not in item
    assert maintainer["username"] == "gitlab-org"
    assert (
        maintainer["avatar_url"] == "https://gitlab.com/api/v4/groups/gitlab-org/avatar"
    )
    assert maintainer["profile_url"] == "https://gitlab.com/gitlab-org"


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
    maintainer = item["maintainer"]

    assert "maintainers" not in item
    assert item["repository_location"] == "https://institution.example.org/team/example"
    assert maintainer["username"] == "team"
    assert maintainer["avatar_url"] is None
    assert item["adapter_id"] == "example-adapter"
