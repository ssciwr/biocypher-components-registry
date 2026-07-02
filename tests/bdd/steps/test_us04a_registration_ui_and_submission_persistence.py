from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when
from typer.testing import CliRunner

from cli import app


scenarios("../features/us04a_registration_ui_and_submission_persistence.feature")


runner = CliRunner()


@pytest.fixture
def registration_context(tmp_path: Path) -> dict[str, Any]:
    """Provide shared state for registration submission scenarios."""
    database_path = tmp_path / "registry.sqlite3"
    repository = tmp_path / "adapter-repo"
    return {
        "database_path": database_path,
        "repository_path": repository,
    }


@given("the maintainer has a valid local adapter repository")
def valid_local_repository(registration_context: dict[str, Any]) -> None:
    """Create a valid local repository path for the submitted adapter."""
    repository = registration_context["repository_path"]
    repository.mkdir()
    registration_context["repository_location"] = str(repository)


@when("the maintainer stores a valid adapter registration from the CLI")
def store_valid_adapter_registration_from_cli(
    registration_context: dict[str, Any],
) -> None:
    """Persist the registration through the terminal command."""
    result = runner.invoke(
        app,
        [
            "submit-registration",
            "--name",
            "Clinical Knowledge Adapter",
            str(registration_context["repository_path"]),
            "--db-path",
            str(registration_context["database_path"]),
        ],
    )
    registration_context["cli_result"] = result


@then("the system stores the submission in the database")
def submission_is_stored(registration_context: dict[str, Any]) -> None:
    """Assert that the submitted registration is persisted in SQLite."""
    with sqlite3.connect(registration_context["database_path"]) as connection:
        row = connection.execute(
            """
            SELECT submitted_adapter_name, repository_location, source_kind
            FROM registration_sources
            """
        ).fetchone()

    assert row == (
        "Clinical Knowledge Adapter",
        str(registration_context["repository_path"].resolve()),
        "local",
    )


@then("the submission receives a tracked registration status from the CLI")
def submission_receives_status_from_cli(
    registration_context: dict[str, Any],
) -> None:
    """Assert that the CLI reports the stored submission status."""
    result = registration_context["cli_result"]

    assert result.exit_code == 0
    assert "Stored Registration" in result.output
    assert "Registration stored" in result.output
    assert "SUBMITTED" in result.output
