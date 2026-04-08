"""
Custom exception classes for the core package.
"""

class MetadataDiscoveryError(Exception):
    """Raised when croissant.jsonld cannot be uniquely located or loaded."""


class RemoteResourceNotFoundError(FileNotFoundError):
    """
    Raised when a remote resource is not found (HTTP 404).

    Attributes:
        url (str): The URL that returned 404.
        status_code (int): The HTTP status code (expected 404).
    """

    def __init__(
        self, url: str, status_code: int = 404, message: str | None = None
    ) -> None:
        self.url = url
        self.status_code = status_code
        if message is None:
            message = f"Remote resource not found ({status_code}) for {url}"
        super().__init__(message)


class InvalidRepoURLError(ValueError):
    """
    Raised when a repository URL is invalid or unsupported.

    Attributes:
        repo_url (str): The invalid repository URL.
    """

    def __init__(self, repo_url: str) -> None:
        self.repo_url = repo_url
        super().__init__(f"Invalid repository URL: {repo_url}")


class MetadataNotFoundError(RemoteResourceNotFoundError):
    """
    Raised when metadata is not found in any expected branch.

    Attributes:
        repo_url (str): The repository URL that was checked.
    """

    def __init__(self, repo_url: str) -> None:
        super().__init__(
            repo_url,
            status_code=404,
            message="Metadata file not found at repo root in 'main' or 'master' branch",
        )
