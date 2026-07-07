from __future__ import annotations

import pytest

from src.api.schemas.adapters import AdapterMaintainerResponse, _repository_url


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
