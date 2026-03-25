from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from src.core.shared.constants import METADATA_FILENAME
from src.core.shared.files import fetch_local_metadata


scenarios("../features/us01_adapter_metadata.feature")


@pytest.fixture
def repo_dir(tmp_path: Path) -> Path:
    return tmp_path / "adapter_repo"


@pytest.fixture
def discovery_context() -> dict[str, object]:
    return {}


@given("an adapter repository with exactly one croissant.jsonld")
def repo_with_single_metadata(repo_dir: Path) -> Path:
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / METADATA_FILENAME).write_text('{"name": "example"}', encoding="utf-8")
    return repo_dir


@given("an adapter repository with no croissant.jsonld")
def repo_with_no_metadata(repo_dir: Path) -> Path:
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "README.md").write_text("no metadata", encoding="utf-8")
    return repo_dir


@given("an adapter repository with multiple croissant.jsonld")
def repo_with_multiple_metadata(repo_dir: Path) -> Path:
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / METADATA_FILENAME).write_text('{"name": "root"}', encoding="utf-8")
    nested = repo_dir / "nested"
    nested.mkdir()
    (nested / METADATA_FILENAME).write_text('{"name": "nested"}', encoding="utf-8")
    return repo_dir


@given("an adapter repository with a croissant.jsonld containing invalid JSON")
def repo_with_invalid_json(repo_dir: Path) -> Path:
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / METADATA_FILENAME).write_text("{invalid json", encoding="utf-8")
    return repo_dir


@when("I run metadata discovery")
def run_discovery(repo_dir: Path, discovery_context: dict[str, object]) -> None:
    try:
        path, metadata = fetch_local_metadata(repo_dir)
        discovery_context["result"] = (path, metadata)
        discovery_context["error"] = None
    except Exception as exc:  # noqa: BLE001 - required for generic step
        discovery_context["result"] = None
        discovery_context["error"] = exc


@then("discovery succeeds")
def discovery_succeeds(discovery_context: dict[str, object]) -> None:
    assert discovery_context["error"] is None
    assert discovery_context["result"] is not None


@then("the metadata is parsed")
def metadata_is_parsed(discovery_context: dict[str, object]) -> None:
    path, metadata = discovery_context["result"]
    assert isinstance(path, Path)
    assert isinstance(metadata, dict)
    assert metadata


@then("discovery fails with a not-found error")
def discovery_fails_not_found(discovery_context: dict[str, object]) -> None:
    error = discovery_context["error"]
    assert isinstance(error, FileNotFoundError)


@then("discovery fails with an ambiguous-file error")
def discovery_fails_ambiguous(discovery_context: dict[str, object]) -> None:
    error = discovery_context["error"]
    assert isinstance(error, ValueError)
    assert "Multiple" in str(error)


@then("the error lists the matching paths")
def error_lists_paths(discovery_context: dict[str, object]) -> None:
    error = discovery_context["error"]
    assert error is not None
    message = str(error)
    assert METADATA_FILENAME in message
    assert "nested" in message


@then("discovery fails with a JSON parsing error")
def discovery_fails_json(discovery_context: dict[str, object]) -> None:
    error = discovery_context["error"]
    assert isinstance(error, ValueError)
    assert "Invalid JSON" in str(error)


@then("the error mentions the file path")
def error_mentions_path(discovery_context: dict[str, object], repo_dir: Path) -> None:
    error = discovery_context["error"]
    assert error is not None
    assert str(repo_dir / METADATA_FILENAME) in str(error)
