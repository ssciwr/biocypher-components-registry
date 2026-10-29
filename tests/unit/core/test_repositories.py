"""Git transport tests use real local Git objects without external hosts."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.core.shared import repositories
from src.core.shared.errors import (
    InvalidRepoURLError,
    MetadataNotFoundError,
    RepositoryUnavailableError,
)


def git(repository: Path, *arguments: str) -> bytes:
    return subprocess.run(
        [
            "git",
            "-c",
            "user.name=Registry tests",
            "-c",
            "user.email=registry@example.org",
            "-c",
            "core.hooksPath=/dev/null",
            "-C",
            str(repository),
            *arguments,
        ],
        check=True,
        capture_output=True,
    ).stdout


@pytest.fixture
def remote_repository(tmp_path, monkeypatch):
    repository = tmp_path / "remote"
    subprocess.run(
        ["git", "init", "-b", "develop", str(repository)],
        check=True,
        capture_output=True,
    )
    (repository / "croissant.jsonld").write_text('{"name":"first"}')
    git(repository, "add", ".")
    git(repository, "commit", "-m", "Initial metadata")
    run_git = repositories._run_git

    def local_transport(arguments, deadline):
        rewritten = [
            str(repository) if item == "https://github.com/org/repo.git" else item
            for item in arguments
        ]
        return run_git(["-c", "protocol.file.allow=always", *rewritten], deadline)

    monkeypatch.setattr(repositories, "_run_git", local_transport)
    return repository


@pytest.mark.parametrize(
    "url, expected",
    [
        (
            "https://github.com/org/repo/blob/feature/metadata.json",
            "https://github.com/org/repo",
        ),
        (
            "https://raw.githubusercontent.com/org/repo/main/croissant.jsonld",
            "https://github.com/org/repo",
        ),
        ("github.com/org/repo.git/", "https://github.com/org/repo"),
        (
            "https://gitlab.example.org/group/subgroup/repo/-/raw/dev/croissant.jsonld?x=1#file",
            "https://gitlab.example.org/group/subgroup/repo",
        ),
        (
            "https://gitlab.example.org/group/subgroup/repo.git",
            "https://gitlab.example.org/group/subgroup/repo",
        ),
    ],
)
def test_normalize_repository_links(url, expected):
    assert repositories.normalize_repository_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "ftp://github.com/org/repo",
        "file:///tmp/repo",
        "https://user:secret@github.com/org/repo",
        "https://github.com/org",
        "https://gitlab.example.org:bad/group/repo",
    ],
)
def test_invalid_urls_and_embedded_credentials_are_rejected(url):
    with pytest.raises(InvalidRepoURLError):
        repositories.normalize_repository_url(url)


def test_snapshot_resolves_actual_default_branch_and_pins_metadata(remote_repository):
    with repositories.repository_snapshot(
        "https://github.com/org/repo/blob/main/croissant.jsonld"
    ) as snapshot:
        directory = Path(snapshot.directory)
        assert snapshot.has_metadata()
        (remote_repository / "croissant.jsonld").write_text('{"name":"second"}')
        git(remote_repository, "commit", "-am", "Change metadata")
        assert snapshot.read_metadata() == '{"name":"first"}'
        assert not (directory / "croissant.jsonld").exists()
    assert not directory.exists()
    with repositories.repository_snapshot("https://github.com/org/repo") as snapshot:
        assert snapshot.read_metadata() == '{"name":"second"}'


def test_missing_file_is_proven_by_tree_and_not_guessed(remote_repository):
    (remote_repository / "croissant.jsonld").unlink()
    git(remote_repository, "commit", "-am", "Remove metadata")
    with repositories.repository_snapshot("https://github.com/org/repo") as snapshot:
        assert not snapshot.has_metadata()
        with pytest.raises(MetadataNotFoundError):
            snapshot.read_metadata()


def test_metadata_size_limit_and_cleanup(remote_repository, monkeypatch):
    monkeypatch.setattr(repositories, "MAX_METADATA_BYTES", 4)
    with (
        pytest.raises(RepositoryUnavailableError) as caught,
        repositories.repository_snapshot("https://github.com/org/repo") as snapshot,
    ):
        directory = Path(snapshot.directory)
        snapshot.read_metadata()
    assert caught.value.reason_code == "METADATA_TOO_LARGE"
    assert not directory.exists()


def test_unresolvable_default_branch_is_not_metadata_absence(monkeypatch):
    monkeypatch.setattr(repositories, "_run_git", Mock(return_value=b""))
    with (
        pytest.raises(RepositoryUnavailableError) as caught,
        repositories.repository_snapshot("https://github.com/org/repo"),
    ):
        pass
    assert caught.value.reason_code == "DEFAULT_BRANCH_UNRESOLVED"


@pytest.mark.parametrize(
    "error, reason",
    [
        (b"repository not found", "REPOSITORY_UNAVAILABLE"),
        (b"HTTP 503", "REMOTE_TEMPORARY"),
    ],
)
def test_git_access_errors_are_unavailable_not_not_found(monkeypatch, error, reason):
    process = Mock(returncode=128)
    process.communicate.return_value = (b"", error)
    monkeypatch.setattr(repositories.subprocess, "Popen", Mock(return_value=process))
    with pytest.raises(RepositoryUnavailableError) as caught:
        repositories._run_git(
            ["ls-remote", "https://github.com/org/repo"], time.monotonic() + 60
        )
    assert caught.value.reason_code == reason


def test_git_timeout_terminates_children(monkeypatch):
    process = Mock(pid=123)
    process.communicate.side_effect = [subprocess.TimeoutExpired("git", 15), (b"", b"")]
    monkeypatch.setattr(repositories.subprocess, "Popen", Mock(return_value=process))
    terminate = Mock()
    monkeypatch.setattr(repositories.os, "killpg", terminate)
    with pytest.raises(RepositoryUnavailableError) as caught:
        repositories._run_git(
            ["ls-remote", "https://github.com/org/repo"], time.monotonic() + 60
        )
    assert caught.value.reason_code == "REMOTE_TEMPORARY"
    terminate.assert_called_once()


def test_git_does_not_inherit_ambient_repository_configuration(monkeypatch):
    monkeypatch.setenv("GIT_DIR", "/private/repository")
    process = Mock(returncode=0)
    process.communicate.return_value = (b"result", b"")
    launch = Mock(return_value=process)
    monkeypatch.setattr(repositories.subprocess, "Popen", launch)
    repositories._run_git(
        ["ls-remote", "https://github.com/org/repo"], time.monotonic() + 60
    )
    environment = launch.call_args.kwargs["env"]
    assert "GIT_DIR" not in environment
    assert environment["GIT_TERMINAL_PROMPT"] == "0"
    assert environment["GIT_CONFIG_GLOBAL"] == "/dev/null"


def test_server_rejecting_filtering_falls_back_to_shallow_fetch(
    remote_repository, monkeypatch
):
    transport = repositories._run_git
    calls = []

    def rejecting_filter(arguments, deadline):
        calls.append(arguments)
        if "--filter=blob:none" in arguments:
            raise RepositoryUnavailableError(
                "Filtering unsupported.", "GIT_FILTER_UNSUPPORTED"
            )
        return transport(arguments, deadline)

    monkeypatch.setattr(repositories, "_run_git", rejecting_filter)
    with repositories.repository_snapshot("https://github.com/org/repo") as snapshot:
        assert snapshot.read_metadata() == '{"name":"first"}'
    assert any("fetch" in call and "--filter=blob:none" not in call for call in calls)
