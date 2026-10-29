"""Service helpers for adapter generation and repository submission."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from src.core.adapter.backends import (
    list_adapter_generators,
    resolve_adapter_generator,
)
from src.core.adapter.request import (
    AdapterGenerationRequest,
    AdapterRegistrationRequest,
)
from src.core.dataset.request import GenerationResult
from src.core.shared.errors import GeneratorError, InvalidRepoURLError


def ensure_supported_generator(generator: str) -> str:
    """Validate that the requested adapter generator is registered."""
    supported_generators = list_adapter_generators()
    if generator not in supported_generators:
        supported = ", ".join(supported_generators)
        raise ValueError(
            f"Unsupported adapter generator '{generator}'. Supported: {supported}."
        )
    return generator


def execute_request(
    request: AdapterGenerationRequest,
    generator: str,
) -> GenerationResult:
    """Execute an adapter generation request with the selected backend."""
    ensure_supported_generator(generator)
    try:
        resolved = resolve_adapter_generator(generator)
        return resolved.generate(request=request)
    except GeneratorError as exc:
        raise RuntimeError(str(exc)) from exc


def create_registration_request(
    repository_location: str,
    description: str | None = None,
    license_value: str | None = None,
    doi: str | None = None,
    cff_url: str | None = None,
    submitted_by_github_user_id: str | None = None,
) -> AdapterRegistrationRequest:
    """Create a normalized adapter registration request.

    Args:
        repository_location: Local repository path or remote repository URL.
        description: Optional maintainer-facing adapter summary.
        license_value: Optional submitted adapter license text.
        doi: Optional submitted DOI text.
        cff_url: Optional submitted Citation File Format URL.
        submitted_by_github_user_id: GitHub user id for browser submissions.

    Returns:
        A normalized registration request ready for the registry workflow.

    Raises:
        ValueError: If the repository location is empty.
        FileNotFoundError: If a submitted local repository path does not exist.
        InvalidRepoURLError: If a submitted URL is not a valid remote repository URL.
    """
    normalized_location = _normalize_repository_into_pure_branchless_location(
        repository_location
    )
    if not normalized_location:
        raise ValueError("Repository location is required.")

    normalized_description = _normalize_optional_text(description)
    normalized_license_value = _normalize_optional_text(license_value)
    normalized_doi = _normalize_optional_text(doi)
    normalized_cff_url = _normalize_optional_text(cff_url)

    if urlparse(normalized_location).scheme:
        _validate_remote_repository(normalized_location)
        repository_kind = "remote"
        normalized_repository_location = normalized_location
    else:
        normalized_repository_location = _normalize_local_repository(
            normalized_location
        )
        repository_kind = "local"

    temporary_adapter_id = (
        uuid4().hex
    )  # ID does not need to be related to the name/content
    return AdapterRegistrationRequest(
        adapter_name=temporary_adapter_id,  # This gets overwritten by the next /registrations/x/process call.
        adapter_id=temporary_adapter_id,
        repository_location=normalized_repository_location,
        repository_kind=repository_kind,
        source=repository_location,
        description=normalized_description,
        license_value=normalized_license_value,
        doi=normalized_doi,
        cff_url=normalized_cff_url,
        submitted_by_github_user_id=submitted_by_github_user_id,
    )


def _normalize_repository_into_pure_branchless_location(
    repository_location: str,
) -> str:
    normalized_location = repository_location.strip()
    if urlparse(normalized_location).scheme or normalized_location.startswith(
        ("github.com/", "gitlab.com/")
    ):
        from src.core.shared.repositories import normalize_repository_url

        return normalize_repository_url(normalized_location)
    return normalized_location


def _normalize_optional_text(value: str | None) -> str | None:
    """Return stripped optional text."""
    if value is None:
        return None
    normalized_value = value.strip()
    return normalized_value or None


def _normalize_local_repository(repository_location: str) -> str:
    """Return a canonical local repository path."""
    repository_path = Path(repository_location).expanduser().resolve()
    if not repository_path.exists():
        raise FileNotFoundError(f"Repository path not found: {repository_location}")
    return str(repository_path)


def _validate_remote_repository(repository_location: str) -> None:
    """Validate that a remote repository URL can be fetched over HTTPS."""
    parsed = urlparse(repository_location)
    if parsed.scheme != "https" or not parsed.netloc:
        raise InvalidRepoURLError(repository_location)
