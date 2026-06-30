from __future__ import annotations

from unittest.mock import Mock

import pytest
import requests

from src.api.schemas.adapters import AdapterMaintainerResponse, _repository_url


# ===========================================================
# Adapter Schema Tests
# ===========================================================


@pytest.mark.parametrize(
    ("repository_location", "expected_username"),
    [
        ("https://github.com/biocypher/collectri/", "biocypher"),
        ("https://gitlab.com/gitlab-org/gitlab", "gitlab-org"),
    ],
) # Gitlab example is the second one; we have no real BioCypher Gitlab examples for now.
def test_repository_maintainer_avatar_url_is_public(
    repository_location: str,
    expected_username: str,
) -> None:
    """
    Can we resolve public maintainer avatar URLs from supported repository locations, whether Gitlab or Github repos?
    """
    repository_url = _repository_url(repository_location)
    maintainer = AdapterMaintainerResponse.from_repository_location(repository_location)
    assert repository_url is not None
    assert maintainer is not None
    response = requests.get(maintainer.avatar_url, timeout=5)
    print(maintainer.avatar_url)

    assert maintainer.username == expected_username
    assert maintainer.avatar_url
    assert response.status_code == 200


def test_repository_maintainer_uses_gitlab_group_avatar(monkeypatch) -> None:
    """
    Resolve GitLab owners that are public groups rather than users.
    """
    user_response = Mock(json=Mock(return_value=[]))
    project_response = Mock(
        json=Mock(
            return_value={
                "namespace": {
                    "full_path": "gitlab-org",
                    "avatar_url": "/uploads/group.png",
                    "web_url": "https://gitlab.example.org/groups/gitlab-org",
                }
            }
        )
    ) # based on mock real response
    monkeypatch.setattr(
        "src.api.schemas.adapters.requests.get",
        Mock(side_effect=[user_response, project_response]),
    )
    maintainer = AdapterMaintainerResponse.from_repository_location(
        "https://gitlab.example.org/gitlab-org/gitlab"
    )

    assert maintainer is not None
    assert maintainer.username == "gitlab-org"
    assert maintainer.avatar_url == "https://gitlab.example.org/uploads/group.png"
