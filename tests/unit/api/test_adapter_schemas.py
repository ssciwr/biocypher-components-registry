from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.api.schemas.adapters import (
    AdapterDetailResponse,
    AdapterLatestItemResponse,
    AdapterMaintainerResponse,
    _repository_url,
)
from src.core.registration.models import (
    RegistrationStatus,
    RegistryEntry,
    StoredRegistration,
)

# ===========================================================
# Adapter Schema Tests
# ===========================================================


@pytest.mark.parametrize(
    ("repository_location", "expected_username", "expected_avatar", "expected_profile"),
    [
        (
            "https://github.com/biocypher/collectri/",
            "biocypher",
            "https://github.com/biocypher.png",
            "https://github.com/biocypher",
        ),
        (
            "https://gitlab.com/gitlab-org/gitlab",
            "gitlab-org",
            "https://gitlab.com/api/v4/groups/gitlab-org/avatar",
            "https://gitlab.com/gitlab-org",
        ),
    ],
)
def test_repository_maintainer_uses_repository_owner(
    repository_location: str,
    expected_username: str,
    expected_avatar: str | None,
    expected_profile: str,
) -> None:
    """
    Resolve public maintainer display data from supported repository locations.
    """
    repository_url = _repository_url(repository_location)
    maintainer = AdapterMaintainerResponse.from_repository_location(repository_location)

    assert repository_url is not None
    assert maintainer is not None
    assert maintainer.username == expected_username
    assert maintainer.avatar_url == expected_avatar
    assert maintainer.profile_url == expected_profile


def test_repository_maintainer_ignores_unknown_host_avatar() -> None:
    """
    Keep unknown repository hosts as plain owner links.
    """
    maintainer = AdapterMaintainerResponse.from_repository_location(
        "https://institution.example.org/team/example"
    )

    assert maintainer is not None
    assert maintainer.username == "team"
    assert maintainer.avatar_url is None
    assert maintainer.profile_url == "https://institution.example.org/team"


def test_repository_maintainer_ignores_incomplete_repository_locations() -> None:
    """

    Negative/red testing of invalid submitted information
    Cover unsupported repository location shapes for maintainer display.
    """
    assert AdapterMaintainerResponse.from_repository_location(None) is None
    assert AdapterMaintainerResponse.from_repository_location("not-a-url") is None
    assert (
        AdapterMaintainerResponse.from_repository_location("https://gitlab.com/org")
        is None
    )


def test_adapter_items_use_singular_maintainer_and_keywords() -> None:
    """
    Cover adapter display responses with a string keyword list.
    """
    now = datetime.now(UTC)
    entry = RegistryEntry(
        "e1", "r1", "Example", "example::1.0", now, now, {"keywords": "a, b,, "}
    )
    registration = StoredRegistration(
        "r1",
        "Example",
        "example",
        "github.com/org/repo",
        "remote",
        RegistrationStatus.VALID,
        now,
    )
    latest_item = AdapterLatestItemResponse.from_entry(entry, registration, 2, True)
    detail_item = AdapterDetailResponse.from_entries("example", [entry], registration)

    assert latest_item.maintainer is not None
    assert latest_item.keywords == ["a", "b"]
    assert latest_item.maintainer.username == "org"
    assert latest_item.endorsement_count == 2
    assert latest_item.endorsed_by_current_user is True
    assert detail_item.maintainer is not None
    assert detail_item.maintainer.username == "org"
