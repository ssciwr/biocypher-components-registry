"""
Discovery utilities for croissant.jsonld adapter metadata files.

Provides functions for discovering and loading croissant.jsonld files
from local and remote (GitHub) sources, with clear separation of fetching,
parsing, and error handling.
"""

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from requests import HTTPError, RequestException

from src.core.constants import METADATA_FILENAME
from src.core.exceptions import (
    InvalidRepoURLError,
    MetadataNotFoundError,
    RemoteResourceNotFoundError,
)


def fetch_local_file(path: Path) -> str:
    """
    Fetch file content from the local filesystem.

    Args:
        path (Path): Path to the file to read.

    Returns:
        str: The file content as a string.

    Raises:
        IOError: If the file cannot be read due to I/O or permission issues.
    """
    try:
        with path.open(encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        msg = f"Failed to read local file {path}: {exc}"
        raise IOError(msg) from exc


def fetch_remote_file(url: str) -> str:
    """
    Fetch file content from a remote URL.

    Args:
        url (str): The URL to fetch the file from.

    Returns:
        str: The file content as a string.

    Raises:
        RemoteResourceNotFoundError: If the file is not found (404).
        RequestException: For network or HTTP errors other than 404.
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
    """
    Parse JSON content and handle errors.

    Args:
        content (str): The JSON string to parse.
        source (str): Description or path of the source (for error messages).

    Returns:
        dict: Parsed JSON as a dictionary.

    Raises:
        ValueError: If the content is not valid JSON.
    """
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        msg = f"Invalid JSON in {source}: {exc}"
        raise ValueError(msg) from exc


def fetch_local_metadata(repo_path: str | Path) -> tuple[Path, dict[str, Any]]:
    """
    Locate and load a single croissant.jsonld file in a local repository.

    Args:
        repo_path (str | Path): Path to the local repository or file.

    Returns:
        tuple[Path, dict[str, Any]]: Tuple of (Path to croissant.jsonld, parsed metadata dict).

    Raises:
        FileNotFoundError: If the file or repository does not exist, or no metadata file is found.
        ValueError: If multiple metadata files are found or JSON is invalid.
    """
    root = Path(repo_path)
    if root.is_file() and root.name == METADATA_FILENAME:
        content = fetch_local_file(root)
        metadata = parse_json_metadata(content, str(root))
        return root, metadata

    if not root.exists():
        msg = f"Repository path does not exist: {root}"
        raise FileNotFoundError(msg)

    candidates = list(root.rglob(METADATA_FILENAME))
    if not candidates:
        msg = f"No '{METADATA_FILENAME}' found under {root}."
        raise FileNotFoundError(msg)
    if len(candidates) > 1:
        found = ", ".join(str(p.relative_to(root)) for p in sorted(candidates))
        msg = f"Multiple '{METADATA_FILENAME}' files found: {found}."
        raise ValueError(msg)

    path = candidates[0]
    content = fetch_local_file(path)
    metadata = parse_json_metadata(content, str(path))
    return path, metadata


def fetch_remote_metadata(repo_url: str) -> dict[str, Any]:
    """
    Attempt to fetch croissant.jsonld from the root of the 'main' or 'master' branch of a remote GitHub repository.

    Args:
        repo_url (str): The GitHub repository URL.

    Returns:
        dict[str, Any]: Parsed metadata dictionary.

    Raises:
        ValueError: If the repository URL is invalid.
        MetadataNotFoundError: If the file is not found in either branch.
        RequestException: For network or HTTP errors other than 404.
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
