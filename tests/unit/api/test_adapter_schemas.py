from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.api.schemas.adapters import (
    AdapterLatestItemResponse,
    AdapterMaintainerResponse,
    data_sources_from_metadata,
    _repository_url,
)
from src.core.registration.models import RegistryEntry, RegistrationStatus, StoredRegistration


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
    assert AdapterMaintainerResponse.from_repository_location("https://gitlab.com/org") is None


def test_latest_adapter_item_normalizes_metadata_keywords() -> None:
    """
    Cover latest adapter cards with a string keyword list.
    """
    now = datetime.now(timezone.utc)
    entry = RegistryEntry("e1", "r1", "Example", "example::1.0", now, now, {"keywords": "a, b,, "})
    registration = StoredRegistration("r1", "Example", "example", "github.com/org/repo", "remote", RegistrationStatus.VALID, now)
    item = AdapterLatestItemResponse.from_entry(entry, registration, 2, True)
    assert item.keywords == ["a", "b"]
    assert item.maintainers[0].username == "org"
    assert item.endorsement_count == 2
    assert item.endorsed_by_current_user is True

