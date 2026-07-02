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
            None,
            "https://gitlab.com/gitlab-org",
        ),
    ],
) # GitLab example is the second one; we have no real BioCypher GitLab examples for now.
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


def test_repository_maintainer_supports_self_hosted_gitlab_owner() -> None:
    """
    Resolve self-hosted GitLab owners without a public avatar lookup.
    """
    maintainer = AdapterMaintainerResponse.from_repository_location(
        "https://gitlab.example.org/gitlab-org/gitlab"
    )

    assert maintainer is not None
    assert maintainer.username == "gitlab-org"
    assert maintainer.avatar_url is None
    assert maintainer.profile_url == "https://gitlab.example.org/gitlab-org"
