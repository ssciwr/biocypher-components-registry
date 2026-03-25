"""File and repository helpers for loading adapter metadata documents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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
        resp = requests.get(url, timeout=15)
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
    """Fetch ``croissant.jsonld`` from a supported GitHub repository URL.

    Args:
        repo_url: GitHub repository URL.

    Returns:
        The parsed remote metadata document.
    """
    parsed = urlparse(repo_url)
    if not parsed.netloc or not parsed.path:
        raise InvalidRepoURLError(repo_url)
    if not parsed.netloc.endswith("github.com"):
        raise InvalidRepoURLError(repo_url)

    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 2:
        raise InvalidRepoURLError(repo_url)

    owner, repo = parts[0], parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    branches = ["main", "master"]
    for branch in branches:
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{METADATA_FILENAME}"
        try:
            content = fetch_remote_file(raw_url)
            return parse_json_metadata(content, raw_url)
        except RemoteResourceNotFoundError:
            continue

    raise MetadataNotFoundError(repo_url)


__all__ = [
    "fetch_local_file",
    "fetch_local_metadata",
    "fetch_remote_file",
    "fetch_remote_metadata",
    "parse_json_metadata",
]
