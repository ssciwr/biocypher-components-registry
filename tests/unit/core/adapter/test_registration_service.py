from __future__ import annotations

from pathlib import Path

import pytest

from src.core.adapter.request import AdapterRegistrationRequest
from src.core.adapter.service import create_registration_request
from src.core.shared.errors import InvalidRepoURLError


def test_create_registration_request_normalizes_local_repository(
    tmp_path: Path,
) -> None:
    """Create a local registration request with normalized values."""
    repository = tmp_path / "example-adapter"
    repository.mkdir()

    request = create_registration_request(
        repository_location=f"  {repository}  ",
    )

    assert isinstance(request, AdapterRegistrationRequest)
    assert request.adapter_name == request.adapter_id
    assert len(request.adapter_id) == 32
    assert request.repository_kind == "local"
    assert request.repository_location == str(repository.resolve())
    assert request.repository_path == repository.resolve()
    assert request.source == f"  {repository}  "


def test_create_registration_request_accepts_supported_remote_repository() -> None:
    """Create a remote registration request for a supported GitHub URL."""
    request = create_registration_request(
        repository_location="https://github.com/example/example-adapter",
    )

    assert isinstance(request, AdapterRegistrationRequest)
    assert request.adapter_name == request.adapter_id
    assert len(request.adapter_id) == 32
    assert request.repository_kind == "remote"
    assert request.repository_location == "https://github.com/example/example-adapter"
    assert request.repository_path is None


def test_create_registration_request_generates_unique_temporary_identifiers(
    tmp_path: Path,
) -> None:
    """AI-Generated.

    Generate independent identifiers before Croissant processing.
    """
    repository = tmp_path / "example-adapter"
    repository.mkdir()

    first = create_registration_request(str(repository))
    second = create_registration_request(str(repository))

    assert first.adapter_id == first.adapter_name
    assert len(first.adapter_id) == 32
    assert first.adapter_id != second.adapter_id


def test_create_registration_request_rejects_empty_repository_location() -> None:
    """Reject a submission when the repository location is blank."""
    with pytest.raises(ValueError, match="Repository location is required."):
        create_registration_request(
            repository_location="   ",
        )


def test_create_registration_request_rejects_missing_local_repository() -> None:
    """Reject a submission when the local repository path does not exist."""
    with pytest.raises(FileNotFoundError, match="Repository path not found"):
        create_registration_request(
            repository_location="/data/definitely-missing-adapter-repository",
        )


def test_create_registration_request_rejects_unsupported_remote_repository() -> None:
    """Reject a submission when the remote repository URL scheme is unsupported."""
    with pytest.raises(InvalidRepoURLError):
        create_registration_request(
            repository_location="http://example.com/example/example-adapter",
        )
