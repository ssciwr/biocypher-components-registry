"""Shared exception types used across generation, discovery, and validation."""

from __future__ import annotations

class GeneratorError(RuntimeError):
    """Base error for generation failures."""


class UnsupportedGeneratorError(GeneratorError):
    """Raised when a generator name cannot be resolved."""


class UnsupportedFormatError(GeneratorError):
    """Raised when no format handler supports a file."""


class InputDiscoveryError(GeneratorError):
    """Raised when generation cannot discover usable input files."""


class GenerationValidationError(GeneratorError):
    """Raised when validation should fail generation."""


class MetadataDiscoveryError(Exception):
    """Raised when ``croissant.jsonld`` cannot be uniquely located or loaded."""


class MetadataFileNotFoundError(FileNotFoundError, MetadataDiscoveryError):
    """Raised when no croissant.jsonld can be found for a repository."""


class AmbiguousMetadataFileError(ValueError, MetadataDiscoveryError):
    """Raised when multiple croissant.jsonld files are found."""


class InvalidMetadataJSONError(ValueError, MetadataDiscoveryError):
    """Raised when croissant.jsonld contains invalid JSON."""


class RemoteResourceNotFoundError(FileNotFoundError):
    """Raised when a remote resource is not found."""

    def __init__(
        self, url: str, status_code: int = 404, message: str | None = None
    ) -> None:
        self.url = url
        self.status_code = status_code
        if message is None:
            message = f"Remote resource not found ({status_code}) for {url}"
        super().__init__(message)


class InvalidRepoURLError(ValueError):
    """Raised when a repository URL is invalid or unsupported."""

    def __init__(self, repo_url: str) -> None:
        self.repo_url = repo_url
        super().__init__(f"Invalid repository URL: {repo_url}")


class MetadataNotFoundError(RemoteResourceNotFoundError):
    """Raised when metadata is not found in any expected branch."""

    def __init__(self, repo_url: str) -> None:
        super().__init__(
            repo_url,
            status_code=404,
            message="Metadata file not found at repo root in 'main' or 'master' branch",
        )

__all__ = [
    "AmbiguousMetadataFileError",
    "GenerationValidationError",
    "GeneratorError",
    "InputDiscoveryError",
    "InvalidMetadataJSONError",
    "InvalidRepoURLError",
    "MetadataDiscoveryError",
    "MetadataFileNotFoundError",
    "MetadataNotFoundError",
    "RemoteResourceNotFoundError",
    "UnsupportedFormatError",
    "UnsupportedGeneratorError",
]
