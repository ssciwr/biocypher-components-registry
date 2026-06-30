from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

from requests import RequestException

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


def test_latest_adapter_uses_gitlab_public_avatar_lookup(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """
    Use GitLab public user API when the repository owner is a user.
    """
    response = Mock()
    response.json.return_value = [
        {"username": "alice", "avatar_url": "/uploads/avatar.png", "web_url": "/alice"}
    ]
    monkeypatch.setattr(
        "src.api.schemas.adapters.requests.get",
        Mock(return_value=response),
    )
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
    assert maintainer["avatar_url"] == "https://gitlab.example.org/uploads/avatar.png"
    assert maintainer["profile_url"] == "https://gitlab.example.org/alice"


def test_latest_adapter_omits_maintainer_when_gitlab_lookup_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """
    Do not show a maintainer avatar when public GitLab-style lookup fails.
    """
    response = Mock()
    response.raise_for_status.side_effect = RequestException("not available")
    monkeypatch.setattr(
        "src.api.schemas.adapters.requests.get",
        Mock(return_value=response),
    )
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

    assert item["repository_location"] == "https://institution.example.org/team/example"
    assert item["maintainers"] == []
    assert item["adapter_id"] == "example-adapter"
