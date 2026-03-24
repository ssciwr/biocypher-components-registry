"""
Unit tests for discovery utilities.

Unit test organization:
    - Nominal Case Tests: Test the nominal case where the function is expected to work
      correctly with typical input values.
    - Negative Case Tests: Test cases that involve invalid input values or scenarios
      where the function should handle errors gracefully.
    - Edge Case Tests: Test cases that involve boundary conditions or unusual input
      values that may not be common but should still be handled correctly by the
      function.
    - Regression Unit Tests: Test cases that ensure that previously fixed bugs do not
      reoccur and that existing functionality remains intact after changes to the
      codebase.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from requests import RequestException

from src.core.constants import METADATA_FILENAME
from src.core.discovery import (
    fetch_local_file,
    fetch_local_metadata,
    fetch_remote_file,
    fetch_remote_metadata,
    parse_json_metadata,
)
from src.core.exceptions import (
    InvalidRepoURLError,
    MetadataNotFoundError,
    RemoteResourceNotFoundError,
)


# =============================================================================
# ==== Fixtures and Setup
# =============================================================================
@pytest.fixture
def repo_dir(tmp_path: Path) -> Path:
    """Fixture to create a repository root path."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    return repo


@pytest.fixture
def sample_json() -> str:
    """Fixture to provide valid JSON content."""
    return '{"name": "example"}'


def _make_response(status_code: int, text: str = "") -> Any:
    class _Response:
        def __init__(self, code: int, body: str) -> None:
            self.status_code = code
            self.text = body

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise RequestException("HTTP error")

    return _Response(status_code, text)


# =============================================================================
# ==== Class Test Cases
# =============================================================================
class TestFetchLocalFile:
    """
    Test cases for fetch_local_file.
    """

    # ---- Nominal Case Tests
    def test_nominal_case(self, repo_dir: Path, sample_json: str) -> None:
        """
        Test the nominal case where a local file exists and can be read.
        """
        path = repo_dir / METADATA_FILENAME
        path.write_text(sample_json, encoding="utf-8")

        assert fetch_local_file(path) == sample_json

    # ---- Negative Case Tests
    def test_missing_file(self, repo_dir: Path) -> None:
        """
        Test the case where a local file does not exist.
        """
        path = repo_dir / METADATA_FILENAME
        with pytest.raises(IOError):
            fetch_local_file(path)

    # ---- Edge Case Tests
    def test_empty_file(self, repo_dir: Path) -> None:
        """
        Test the case where a local file is empty.
        """
        path = repo_dir / METADATA_FILENAME
        path.write_text("", encoding="utf-8")

        assert fetch_local_file(path) == ""

    # ---- Regression Unit Tests
    def test_unicode_content(self, repo_dir: Path) -> None:
        """
        Test reading non-ASCII-safe content to ensure encoding handling remains correct.
        """
        path = repo_dir / METADATA_FILENAME
        content = '{"name": "Munchen"}'
        path.write_text(content, encoding="utf-8")

        assert fetch_local_file(path) == content


class TestParseJsonMetadata:
    """
    Test cases for parse_json_metadata.
    """

    # ---- Nominal Case Tests
    def test_nominal_case(self, sample_json: str) -> None:
        """
        Test parsing a valid JSON string.
        """
        parsed = parse_json_metadata(sample_json, "source")
        assert parsed["name"] == "example"

    # ---- Negative Case Tests
    def test_invalid_json(self) -> None:
        """
        Test parsing invalid JSON and receiving a ValueError.
        """
        with pytest.raises(ValueError):
            parse_json_metadata("{invalid", "source")

    # ---- Edge Case Tests
    def test_empty_object(self) -> None:
        """
        Test parsing an empty JSON object.
        """
        parsed = parse_json_metadata("{}", "source")
        assert parsed == {}

    # ---- Regression Unit Tests
    def test_error_message_includes_source(self) -> None:
        """
        Test that parsing errors include the source in the message.
        """
        with pytest.raises(ValueError) as exc_info:
            parse_json_metadata("{invalid", "my-source")
        assert "my-source" in str(exc_info.value)


class TestFetchLocalMetadata:
    """
    Test cases for fetch_local_metadata.
    """

    # ---- Nominal Case Tests
    def test_nominal_case(self, repo_dir: Path, sample_json: str) -> None:
        """
        Test discovery with exactly one metadata file.
        """
        path = repo_dir / METADATA_FILENAME
        path.write_text(sample_json, encoding="utf-8")

        found_path, metadata = fetch_local_metadata(repo_dir)
        assert found_path == path
        assert metadata["name"] == "example"

    # ---- Negative Case Tests
    def test_missing_metadata(self, repo_dir: Path) -> None:
        """
        Test discovery when no metadata file exists.
        """
        with pytest.raises(FileNotFoundError):
            fetch_local_metadata(repo_dir)

    def test_multiple_metadata(self, repo_dir: Path, sample_json: str) -> None:
        """
        Test discovery when multiple metadata files exist.
        """
        (repo_dir / METADATA_FILENAME).write_text(sample_json, encoding="utf-8")
        nested = repo_dir / "nested"
        nested.mkdir()
        (nested / METADATA_FILENAME).write_text(sample_json, encoding="utf-8")

        with pytest.raises(ValueError) as exc_info:
            fetch_local_metadata(repo_dir)
        assert "Multiple" in str(exc_info.value)

    # ---- Edge Case Tests
    def test_direct_file_path(self, repo_dir: Path, sample_json: str) -> None:
        """
        Test discovery when a direct file path is provided.
        """
        path = repo_dir / METADATA_FILENAME
        path.write_text(sample_json, encoding="utf-8")

        found_path, metadata = fetch_local_metadata(path)
        assert found_path == path
        assert metadata["name"] == "example"

    # ---- Regression Unit Tests
    def test_invalid_json(self, repo_dir: Path) -> None:
        """
        Test that invalid JSON in the metadata file raises a ValueError.
        """
        path = repo_dir / METADATA_FILENAME
        path.write_text("{invalid", encoding="utf-8")

        with pytest.raises(ValueError) as exc_info:
            fetch_local_metadata(repo_dir)
        assert str(path) in str(exc_info.value)


class TestFetchRemoteFile:
    """
    Test cases for fetch_remote_file.
    """

    # ---- Nominal Case Tests
    def test_nominal_case(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Test fetching a remote file successfully.
        """
        def fake_get(url: str, timeout: int) -> Any:
            return _make_response(200, "payload")

        monkeypatch.setattr("src.core.discovery.requests.get", fake_get)
        assert fetch_remote_file("https://example.com/file") == "payload"

    # ---- Negative Case Tests
    def test_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Test fetching a remote file that returns 404.
        """
        def fake_get(url: str, timeout: int) -> Any:
            return _make_response(404, "")

        monkeypatch.setattr("src.core.discovery.requests.get", fake_get)
        with pytest.raises(RemoteResourceNotFoundError):
            fetch_remote_file("https://example.com/missing")

    def test_http_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Test fetching a remote file that returns an HTTP error.
        """
        def fake_get(url: str, timeout: int) -> Any:
            return _make_response(500, "")

        monkeypatch.setattr("src.core.discovery.requests.get", fake_get)
        with pytest.raises(RequestException):
            fetch_remote_file("https://example.com/error")

    # ---- Edge Case Tests
    def test_timeout_propagation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Test that request exceptions propagate as RequestException.
        """
        def fake_get(url: str, timeout: int) -> Any:
            raise RequestException("timeout")

        monkeypatch.setattr("src.core.discovery.requests.get", fake_get)
        with pytest.raises(RequestException):
            fetch_remote_file("https://example.com/timeout")

    # ---- Regression Unit Tests
    def test_error_message_contains_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Test error messages include the URL for debugging.
        """
        def fake_get(url: str, timeout: int) -> Any:
            return _make_response(500, "")

        monkeypatch.setattr("src.core.discovery.requests.get", fake_get)
        with pytest.raises(RequestException) as exc_info:
            fetch_remote_file("https://example.com/error")
        assert "https://example.com/error" in str(exc_info.value)


class TestFetchRemoteMetadata:
    """
    Test cases for fetch_remote_metadata.
    """

    # ---- Nominal Case Tests
    def test_nominal_case(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Test remote discovery when metadata exists.
        """
        def fake_fetch(url: str) -> str:
            return '{"name": "remote"}'

        monkeypatch.setattr("src.core.discovery.fetch_remote_file", fake_fetch)
        metadata = fetch_remote_metadata("https://github.com/org/repo")
        assert metadata["name"] == "remote"

    # ---- Negative Case Tests
    def test_invalid_url(self) -> None:
        """
        Test remote discovery when the repository URL is invalid.
        """
        with pytest.raises(InvalidRepoURLError):
            fetch_remote_metadata("not-a-url")

    def test_non_github_url(self) -> None:
        """
        Test remote discovery when the repository URL is not GitHub.
        """
        with pytest.raises(InvalidRepoURLError):
            fetch_remote_metadata("https://gitlab.com/org/repo")

    def test_metadata_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Test remote discovery when metadata is not found in main/master.
        """
        def fake_fetch(url: str) -> str:
            raise RemoteResourceNotFoundError(url)

        monkeypatch.setattr("src.core.discovery.fetch_remote_file", fake_fetch)
        with pytest.raises(MetadataNotFoundError):
            fetch_remote_metadata("https://github.com/org/repo")

    # ---- Edge Case Tests
    def test_repo_url_with_git_suffix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Test remote discovery when the repo URL ends with .git.
        """
        def fake_fetch(url: str) -> str:
            return '{"name": "remote"}'

        monkeypatch.setattr("src.core.discovery.fetch_remote_file", fake_fetch)
        metadata = fetch_remote_metadata("https://github.com/org/repo.git")
        assert metadata["name"] == "remote"

    # ---- Regression Unit Tests
    def test_error_is_specific_type(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Test that missing metadata raises MetadataNotFoundError, not ValueError.
        """
        def fake_fetch(url: str) -> str:
            raise RemoteResourceNotFoundError(url)

        monkeypatch.setattr("src.core.discovery.fetch_remote_file", fake_fetch)
        with pytest.raises(MetadataNotFoundError):
            fetch_remote_metadata("https://github.com/org/repo")
