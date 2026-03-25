"""Service helpers for adapter generation and repository submission."""

from __future__ import annotations

from pathlib import Path

from src.core.adapter.request import (
    AdapterGenerationRequest,
    AdapterRegistrationRequest,
)
from src.core.adapter.backends import (
    list_adapter_generators,
    resolve_adapter_generator,
)
from src.core.dataset.request import GenerationResult
from src.core.shared.errors import GeneratorError, InvalidRepoURLError
from src.core.shared.ids import slugify_identifier


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
    adapter_name: str,
    repository_location: str,
    contact_email: str | None = None,
) -> AdapterRegistrationRequest:
    """Create a normalized adapter registration request.

    Args:
        adapter_name: Human-readable adapter name provided by the maintainer.
        repository_location: Local repository path or supported repository URL.
        contact_email: Optional maintainer contact email for status follow-up.

    Returns:
        A normalized registration request ready for the registry workflow.

    Raises:
        ValueError: If the adapter name or location is empty.
        ValueError: If the contact email is provided but invalid.
        FileNotFoundError: If a submitted local repository path does not exist.
        InvalidRepoURLError: If a submitted URL is not a supported repository URL.
    """
    normalized_name = adapter_name.strip()
    if not normalized_name:
        raise ValueError("Adapter name is required.")

    normalized_location = repository_location.strip()
    if not normalized_location:
        raise ValueError("Repository location is required.")

    normalized_contact_email = _normalize_contact_email(contact_email)

    if normalized_location.startswith(("http://", "https://")):
        _validate_remote_repository(normalized_location)
        repository_kind = "remote"
        normalized_repository_location = normalized_location
    else:
        normalized_repository_location = _normalize_local_repository(
            normalized_location
        )
        repository_kind = "local"

    return AdapterRegistrationRequest(
        adapter_name=normalized_name,
        adapter_id=slugify_identifier(normalized_name),
        repository_location=normalized_repository_location,
        repository_kind=repository_kind,
        source=repository_location,
        contact_email=normalized_contact_email,
    )


def _normalize_contact_email(contact_email: str | None) -> str | None:
    """Return a normalized optional contact email."""
    if contact_email is None:
        return None

    normalized_email = contact_email.strip()
    if not normalized_email:
        return None

    local_part, separator, domain = normalized_email.partition("@")
    if not separator or not local_part or "." not in domain:
        raise ValueError("Contact email must be a valid email address.")

    return normalized_email


def _normalize_local_repository(repository_location: str) -> str:
    """Return a canonical local repository path."""
    repository_path = Path(repository_location).expanduser().resolve()
    if not repository_path.exists():
        raise FileNotFoundError(f"Repository path not found: {repository_location}")
    return str(repository_path)


def _validate_remote_repository(repository_location: str) -> None:
    """Validate that a remote repository URL is currently supported."""
    if "github.com" not in repository_location:
        raise InvalidRepoURLError(repository_location)
