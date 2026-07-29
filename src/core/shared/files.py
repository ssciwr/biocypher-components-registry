"""File and repository helpers for loading adapter metadata documents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import ParseResult, urljoin, urlparse

import requests
from requests import HTTPError, RequestException

from src.core.shared.constants import METADATA_FILENAME
from src.core.shared.errors import (
    AmbiguousMetadataFileError,
    InvalidMetadataJSONError,
    InvalidRepoURLError,
    MetadataFileNotFoundError,
    MetadataNotFoundError,
    RemoteResourceNotFoundError,
)


def fetch_local_file(path: Path) -> str:
    """Read a UTF-8 text file from disk.

    Args:
        path: File to read.

    Returns:
        The file contents as text.

    Raises:
        IOError: If the file cannot be opened or read.
    """
    try:
        with path.open(encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        msg = f"Failed to read local file {path}: {exc}"
        raise IOError(msg) from exc


def fetch_remote_file(url: str) -> str:
    """Fetch a text file over HTTP.

    Args:
        url: Remote URL to fetch.

    Returns:
        The response body as text.
    """
    try:
        # adapter discovery intentionally fetches maintainer-provided repository metadata URLs.
        resp = requests.get(url, timeout=15)  # NOSONAR
        if resp.status_code == 404:
            raise RemoteResourceNotFoundError(url, status_code=404)
        resp.raise_for_status()
        return resp.text
    except HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        msg = f"HTTP error ({status}) for {url}"
        raise RequestException(msg) from exc
    except RequestException as exc:
        msg = f"Failed to fetch remote file {url}: {exc}"
        raise RequestException(msg) from exc


def parse_json_metadata(content: str, source: str) -> dict[str, Any]:
    """Parse JSON metadata and attach the source to parsing errors.

    Args:
        content: Raw JSON payload.
        source: Human-readable source description for error messages.

    Returns:
        The decoded JSON object.
    """
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        msg = f"Invalid JSON in {source}: {exc}"
        raise InvalidMetadataJSONError(msg) from exc


def fetch_local_metadata(repo_path: str | Path) -> tuple[Path, dict[str, Any]]:
    """Locate and parse exactly one local ``croissant.jsonld`` file.

    Args:
        repo_path: Repository root or direct metadata file path.

    Returns:
        A tuple of the resolved metadata path and parsed JSON document.
    """
    root = Path(repo_path)
    if root.is_file() and root.name == METADATA_FILENAME:
        content = fetch_local_file(root)
        metadata = parse_json_metadata(content, str(root))
        return root, metadata

    if not root.exists():
        msg = f"Repository path does not exist: {root}"
        raise MetadataFileNotFoundError(msg)

    candidates = list(root.rglob(METADATA_FILENAME))
    if not candidates:
        msg = f"No '{METADATA_FILENAME}' found under {root}."
        raise MetadataFileNotFoundError(msg)
    if len(candidates) > 1:
        found = ", ".join(str(p.relative_to(root)) for p in sorted(candidates))
        msg = f"Multiple '{METADATA_FILENAME}' files found: {found}."
        raise AmbiguousMetadataFileError(msg)

    path = candidates[0]
    content = fetch_local_file(path)
    metadata = parse_json_metadata(content, str(path))
    return path, metadata


def fetch_remote_metadata(repo_url: str) -> dict[str, Any]:
    """Fetch ``croissant.jsonld`` from a remote repository URL (Github or Gitlab by default)

    Args:
        repo_url: Remote repository URL.

    Returns:
        The parsed remote metadata document.
    """
    parsed = urlparse(repo_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise InvalidRepoURLError(repo_url)

    for metadata_url in _remote_metadata_urls(repo_url, parsed):
        try:
            content = fetch_remote_file(metadata_url)
            return parse_json_metadata(content, metadata_url)
        except RemoteResourceNotFoundError:
            continue

    raise MetadataNotFoundError(repo_url)


def remote_metadata_exists(repo_url: str) -> bool:
    """
    Check whether a remote repository exposes the expected metadata file.
    """
    parsed = urlparse(repo_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise InvalidRepoURLError(repo_url)

    for metadata_url in _remote_metadata_urls(repo_url, parsed):
        try:
            fetch_remote_file(metadata_url)
            return True
        except RemoteResourceNotFoundError:
            continue

    return False


def _remote_metadata_urls(repo_url: str, parsed: ParseResult) -> list[str]:
    """Build candidate croissant URLs without requiring a GitHub-owned repository."""
    normalized_path = parsed.path.rstrip("/")

    if parsed.netloc.lower() == "github.com":
        github_urls = _github_metadata_urls(parsed)
        if github_urls:
            return github_urls

    if "/-/" in normalized_path:
        gitlab_urls = _gitlab_metadata_urls(parsed)
        if gitlab_urls:
            return gitlab_urls

    if normalized_path.endswith(f"/{METADATA_FILENAME}"):
        return [parsed._replace(path=normalized_path).geturl()]

    gitlab_urls = _gitlab_metadata_urls(parsed)
    if gitlab_urls:
        return gitlab_urls

    return [urljoin(repo_url.rstrip("/") + "/", METADATA_FILENAME)]


def _github_metadata_urls(parsed: ParseResult) -> list[str]:
    # treat as typical github url
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 2:
        return []

    owner, repo = parts[0], parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    if len(parts) >= 5 and parts[2] == "blob":
        return [
            "https://raw.githubusercontent.com/"
            f"{owner}/{repo}/{parts[3]}/{'/'.join(parts[4:])}"
        ]
    return [
        f"https://raw.githubusercontent.com/{owner}/{repo}/main/{METADATA_FILENAME}",
        f"https://raw.githubusercontent.com/{owner}/{repo}/master/{METADATA_FILENAME}",
    ]


def _gitlab_metadata_urls(parsed: ParseResult) -> list[str]:
    """Build GitLab raw metadata URLs from project roots or blob/raw file URLs."""
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 2:
        return []

    base_url = f"{parsed.scheme}://{parsed.netloc}"
    if "-" in parts:
        marker = parts.index("-")
        if marker >= 2 and marker + 2 < len(parts) and parts[marker + 1] in {"blob", "raw"}:
            project_path = "/".join(parts[:marker])
            branch = parts[marker + 2]
            return [
                f"{base_url}/{project_path}/-/raw/{branch}/{METADATA_FILENAME}"
            ]
        return []

    owner, repo = parts[0], parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    project_path = f"{owner}/{repo}"
    return [
        f"{base_url}/{project_path}/-/raw/main/{METADATA_FILENAME}",
        f"{base_url}/{project_path}/-/raw/master/{METADATA_FILENAME}",
    ]


__all__ = [
    "fetch_local_file",
    "fetch_local_metadata",
    "fetch_remote_file",
    "fetch_remote_metadata",
    "parse_json_metadata",
    "remote_metadata_exists",
]
