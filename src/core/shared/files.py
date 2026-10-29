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
    MetadataFileNotFoundError,
    RemoteResourceNotFoundError,
)
from src.core.shared.json_source import JSONSource, MetadataDocument
from src.core.shared.repositories import repository_snapshot


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
        raise OSError(msg) from exc


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


def parse_json_metadata(
    content: str, source: str, *, source_url: str | None = None
) -> dict[str, Any]:
    """Parse JSON metadata and attach the source to parsing errors.

    Args:
        content: Raw JSON payload.
        source: Human-readable source description for error messages.

    Returns:
        The decoded JSON object.
    """
    try:
        metadata = json.loads(content)
        if not isinstance(metadata, dict):
            raise InvalidMetadataJSONError(
                f"Metadata in {source} must be a JSON object."
            )
        return MetadataDocument(
            metadata, JSONSource(content, METADATA_FILENAME, source_url)
        )
    except json.JSONDecodeError as exc:
        msg = f"Invalid JSON in {source}: {exc}"
        raise InvalidMetadataJSONError(
            msg,
            line=exc.lineno,
            column=exc.colno,
            source_file=METADATA_FILENAME,
            source_url=source_url,
        ) from exc


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
    """Read root metadata from the repository's resolved default-branch commit."""
    with repository_snapshot(repo_url) as snapshot:
        source_url = (
            f"{snapshot.repository_url}/blob/{snapshot.commit}/{METADATA_FILENAME}"
            if urlparse(snapshot.repository_url).hostname == "github.com"
            and isinstance(snapshot.commit, str)
            else None
        )
        return parse_json_metadata(
            snapshot.read_metadata(), snapshot.repository_url, source_url=source_url
        )


def remote_metadata_exists(repo_url: str) -> bool:
    """Inspect the root tree; access failures must not be reported as absence."""
    with repository_snapshot(repo_url, root_only=True) as snapshot:
        return snapshot.has_metadata()


__all__ = [
    "fetch_local_file",
    "fetch_local_metadata",
    "fetch_remote_file",
    "fetch_remote_metadata",
    "parse_json_metadata",
    "remote_metadata_exists",
]
