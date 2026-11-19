"""Public repository endpoints must not connect to arbitrary internal hosts."""

from unittest.mock import Mock

import pytest

from src.core.shared import repositories
from src.core.shared.errors import InvalidRepoURLError


@pytest.mark.parametrize(
    "host",
    [
        "127.0.0.1:8443",
        "10.0.0.1",
        "[::1]",
        "localhost",
        "github.com.attacker.example",
        "github.com:8443",
    ],
)
def test_unapproved_hosts_are_rejected_before_git(host, monkeypatch):
    run = Mock()
    monkeypatch.setattr(repositories, "_run_git", run)
    with (
        pytest.raises(InvalidRepoURLError),
        repositories.repository_snapshot(f"https://{host}/group/repo"),
    ):
        pass
    run.assert_not_called()


def test_explicitly_approved_self_hosted_repository_is_supported(monkeypatch):
    monkeypatch.setenv(
        "REGISTRY_ALLOWED_REPOSITORY_HOSTS", "github.com,gitlab.example.org"
    )
    assert (
        repositories.normalize_repository_url("https://gitlab.example.org/group/repo")
        == "https://gitlab.example.org/group/repo"
    )


def test_private_literal_is_rejected_even_if_configured(monkeypatch):
    monkeypatch.setenv("REGISTRY_ALLOWED_REPOSITORY_HOSTS", "127.0.0.1")
    with pytest.raises(InvalidRepoURLError):
        repositories.normalize_repository_url("https://127.0.0.1/group/repo")
