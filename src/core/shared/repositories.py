"""Normalize repository links and inspect immutable snapshots over Git HTTPS."""

from __future__ import annotations

import os
import re
import signal
import subprocess
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from urllib.parse import urlparse

from src.core.shared.constants import METADATA_FILENAME
from src.core.shared.errors import (
    InvalidRepoURLError,
    MetadataNotFoundError,
    RepositoryUnavailableError,
)

GIT_COMMAND_TIMEOUT = 15
GIT_OPERATION_TIMEOUT = 60
MAX_METADATA_BYTES = 5 * 1024 * 1024


def normalize_repository_url(value: str) -> str:
    """Discard file/branch routes while preserving nested GitLab namespaces."""
    value = value.strip()
    if value.startswith(("github.com/", "gitlab.com/")):
        value = f"https://{value}"
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise InvalidRepoURLError(value)
    try:
        _ = parsed.port
    except ValueError as exc:
        raise InvalidRepoURLError(value) from exc
    parts = [part for part in parsed.path.split("/") if part]
    host = parsed.netloc.lower()
    if parsed.hostname.lower() in {"github.com", "raw.githubusercontent.com"}:
        host = "github.com"
        parts = parts[:2]
    elif "-" in parts:
        parts = parts[: parts.index("-")]
    if len(parts) < 2 or any(part in {".", ".."} for part in parts):
        raise InvalidRepoURLError(value)
    parts[-1] = parts[-1].removesuffix(".git")
    if not parts[-1]:
        raise InvalidRepoURLError(value)
    return f"https://{host}/{'/'.join(parts)}"


def _run_git(arguments: list[str], deadline: float) -> bytes:
    """Run isolated, noninteractive Git and terminate its children on timeout."""
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RepositoryUnavailableError(
            "Repository check timed out. Try again.", "REMOTE_TEMPORARY"
        )
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    environment.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_TERMINAL_PROMPT="0",
        GIT_ASKPASS="/bin/false",
    )
    command = [
        "git",
        "-c",
        "protocol.allow=never",
        "-c",
        "protocol.https.allow=always",
        "-c",
        "credential.helper=",
        "-c",
        f"core.hooksPath={os.devnull}",
        "-c",
        "http.followRedirects=false",
        *arguments,
    ]
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            start_new_session=True,
        )
    except OSError as exc:
        raise RepositoryUnavailableError(
            "Git transport is unavailable on the server."
        ) from exc
    try:
        output, errors = process.communicate(
            timeout=min(GIT_COMMAND_TIMEOUT, remaining)
        )
    except subprocess.TimeoutExpired as exc:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass  # The process may have exited just as its timeout expired.
        process.communicate()
        raise RepositoryUnavailableError(
            "Repository check timed out. Try again.", "REMOTE_TEMPORARY"
        ) from exc
    if process.returncode:
        detail = errors.decode("utf-8", errors="replace").lower()
        if "filter" in detail and (
            "not supported" in detail or "does not support" in detail
        ):
            raise RepositoryUnavailableError(
                "Git filtering is unsupported by this host.", "GIT_FILTER_UNSUPPORTED"
            )
        transient = any(
            word in detail
            for word in (
                "429",
                "500",
                "502",
                "503",
                "504",
                "timed out",
                "could not resolve",
                "failed to connect",
                "connection reset",
                "rate limit",
            )
        )
        raise RepositoryUnavailableError(
            "The repository host is temporarily unavailable. Try again."
            if transient
            else "Could not access the repository. It may be private, restricted, or unavailable.",
            "REMOTE_TEMPORARY" if transient else "REPOSITORY_UNAVAILABLE",
        )
    return output


@dataclass(frozen=True)
class RepositorySnapshot:
    """One resolved commit, shared by inspection and metadata reads."""

    repository_url: str
    directory: str
    commit: str
    deadline: float

    def has_metadata(self) -> bool:
        tree = _run_git(
            [
                "-C",
                self.directory,
                "ls-tree",
                "-z",
                self.commit,
                "--",
                METADATA_FILENAME,
            ],
            self.deadline,
        )
        # A directory or symbolic link named croissant.jsonld is not a metadata file.
        return tree.startswith((b"100644 blob ", b"100755 blob "))

    def read_metadata(self) -> str:
        if not self.has_metadata():
            raise MetadataNotFoundError(self.repository_url)
        object_name = f"{self.commit}:{METADATA_FILENAME}"
        size = int(
            _run_git(
                ["-C", self.directory, "cat-file", "-s", object_name], self.deadline
            )
        )
        if size > MAX_METADATA_BYTES:
            raise RepositoryUnavailableError(
                "The metadata file exceeds the 5 MiB limit.", "METADATA_TOO_LARGE"
            )
        content = _run_git(
            ["-C", self.directory, "cat-file", "blob", object_name], self.deadline
        )
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError as exc:
            from src.core.shared.errors import InvalidMetadataJSONError

            raise InvalidMetadataJSONError(
                "Metadata must be UTF-8 encoded JSON."
            ) from exc


@contextmanager
def repository_snapshot(repository_url: str) -> Iterator[RepositorySnapshot]:
    """Resolve default HEAD and fetch only its snapshot, without a checkout."""
    normalized = normalize_repository_url(repository_url)
    # GitLab redirects project-root Git requests to this canonical endpoint.
    # Address it directly so arbitrary HTTP redirects can remain disabled.
    transport_url = f"{normalized}.git"
    deadline = time.monotonic() + GIT_OPERATION_TIMEOUT
    references = _run_git(
        ["ls-remote", "--symref", transport_url, "HEAD"], deadline
    ).decode()
    branch = re.search(r"^ref: refs/heads/([^\t\n]+)\tHEAD$", references, re.MULTILINE)
    commit = re.search(r"^([0-9a-f]{40,64})\tHEAD$", references, re.MULTILINE)
    if branch is None or commit is None:
        raise RepositoryUnavailableError(
            "Could not resolve the repository's default branch.",
            "DEFAULT_BRANCH_UNRESOLVED",
        )
    with tempfile.TemporaryDirectory(prefix="registry-git-") as directory:
        _run_git(["init", "--bare", directory], deadline)
        _run_git(["-C", directory, "remote", "add", "origin", transport_url], deadline)
        _run_git(
            ["-C", directory, "config", "remote.origin.promisor", "true"], deadline
        )
        _run_git(
            [
                "-C",
                directory,
                "config",
                "remote.origin.partialclonefilter",
                "blob:none",
            ],
            deadline,
        )
        # Git falls back to an ordinary shallow transfer when a server ignores filtering.
        fetch = ["-C", directory, "fetch", "--quiet", "--depth=1", "--no-tags"]
        try:
            _run_git(
                [*fetch, "--filter=blob:none", "origin", commit.group(1)], deadline
            )
        except RepositoryUnavailableError as exc:
            if exc.reason_code != "GIT_FILTER_UNSUPPORTED":
                raise
            _run_git(
                [
                    "-C",
                    directory,
                    "config",
                    "--unset",
                    "remote.origin.partialclonefilter",
                ],
                deadline,
            )
            _run_git([*fetch, "origin", commit.group(1)], deadline)
        yield RepositorySnapshot(normalized, directory, commit.group(1), deadline)
