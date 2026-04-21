from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.core.adapter.request import AdapterRegistrationRequest
from src.core.adapter.service import create_registration_request


scenarios("../features/us04_repository_submission.feature")


@pytest.fixture
def submission_context() -> dict[str, Any]:
    """Provide shared mutable state for repository submission scenarios."""
    return {}


@given(
    parsers.parse('a maintainer wants to register an adapter named "{adapter_name}"')
)
def valid_adapter_name(
    submission_context: dict[str, Any],
    adapter_name: str,
) -> None:
    """Store the submitted adapter name in the scenario context."""
    submission_context["adapter_name"] = adapter_name


@given("the maintainer provides a local repository location")
def local_repository_location(
    tmp_path: Path,
    submission_context: dict[str, Any],
) -> None:
    """Store a valid local repository path in the scenario context."""
    repository = tmp_path / "clinical-knowledge-adapter"
    repository.mkdir()
    submission_context["repository_location"] = str(repository)


@given("the maintainer provides a supported repository URL")
def supported_repository_url(submission_context: dict[str, Any]) -> None:
    """Store a supported repository URL in the scenario context."""
    submission_context["repository_location"] = (
        "https://github.com/example/clinical-knowledge-adapter"
    )


@when("the maintainer submits the adapter registration")
def repository_submission_is_accepted(submission_context: dict[str, Any]) -> None:
    """Create a registration request from the submitted repository details."""
    submission_context["request"] = create_registration_request(
        adapter_name=submission_context["adapter_name"],
        repository_location=submission_context["repository_location"],
    )


@then("the system creates a local registration request for that adapter")
def system_creates_local_registration_request(
    submission_context: dict[str, Any],
) -> None:
    """Assert that a normalized local registration request is created."""
    request = submission_context["request"]

    assert isinstance(request, AdapterRegistrationRequest)
    assert request.adapter_name == submission_context["adapter_name"]
    assert request.adapter_id == "clinical-knowledge-adapter"
    assert request.repository_kind == "local"
    assert request.repository_path is not None
    assert request.repository_path.is_dir()


@then("the system creates a remote registration request for that adapter")
def system_creates_remote_registration_request(
    submission_context: dict[str, Any],
) -> None:
    """Assert that a normalized remote registration request is created."""
    request = submission_context["request"]

    assert isinstance(request, AdapterRegistrationRequest)
    assert request.adapter_name == submission_context["adapter_name"]
    assert request.adapter_id == "clinical-knowledge-adapter"
    assert request.repository_kind == "remote"
    assert request.repository_location == submission_context["repository_location"]
    assert request.repository_path is None
