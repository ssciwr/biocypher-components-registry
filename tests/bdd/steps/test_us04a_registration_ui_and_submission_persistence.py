from __future__ import annotations

import io
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when
from typer.testing import CliRunner

from cli import app
from src.core.web import server as web_ui_new


scenarios("../features/us04a_registration_ui_and_submission_persistence.feature")


runner = CliRunner()


@pytest.fixture
def registration_context(tmp_path: Path) -> dict[str, Any]:
    """Provide shared state for registration UI scenarios."""
    database_path = tmp_path / "registry.sqlite3"
    repository = tmp_path / "adapter-repo"
    return {
        "database_path": database_path,
        "repository_path": repository,
    }


@given("a maintainer opens the registration interface")
def maintainer_opens_registration_interface(
    registration_context: dict[str, Any],
) -> None:
    """Render the registration page through the lightweight web handler."""
    handler = web_ui_new._Handler
    handler.output_dir = Path(".")
    handler.last_output_path = Path(".") / "croissant.jsonld"
    handler.registration_db_path = registration_context["database_path"]

    get_handler = object.__new__(handler)
    get_handler.path = "/register"
    get_handler.wfile = io.BytesIO()
    captured: list[tuple[int, str]] = []
    get_handler._send = lambda content, status=200: captured.append((status, content))

    handler.do_GET(get_handler)

    registration_context["get_response"] = captured


@given("the maintainer has a valid local adapter repository")
def valid_local_repository(registration_context: dict[str, Any]) -> None:
    """Create a valid local repository path for the submitted adapter."""
    repository = registration_context["repository_path"]
    repository.mkdir()
    registration_context["repository_location"] = str(repository)


@given("the maintainer has a supported adapter repository URL")
def supported_repository_url(registration_context: dict[str, Any]) -> None:
    """Store a supported remote repository URL for the submitted adapter."""
    registration_context["repository_location"] = (
        "https://github.com/example/clinical-knowledge-adapter"
    )


@when("the maintainer submits a valid adapter name and repository location")
def submit_valid_adapter_registration(
    registration_context: dict[str, Any],
) -> None:
    """Submit the registration form through the lightweight web handler."""
    handler = web_ui_new._Handler
    handler.output_dir = Path(".")
    handler.last_output_path = Path(".") / "croissant.jsonld"
    handler.registration_db_path = registration_context["database_path"]

    body = (
        "adapter_name=Clinical+Knowledge+Adapter&"
        "confirm_croissant_root=yes&"
        f"repository_location={registration_context['repository_location']}"
    ).encode("utf-8")

    post_handler = object.__new__(handler)
    post_handler.path = "/register"
    post_handler.headers = {"Content-Length": str(len(body))}
    post_handler.rfile = io.BytesIO(body)
    captured: list[tuple[int, str]] = []
    post_handler._send = lambda content, status=200: captured.append((status, content))

    handler.do_POST(post_handler)

    registration_context["post_response"] = captured


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


@then("the system stores the remote submission in the database")
def remote_submission_is_stored(registration_context: dict[str, Any]) -> None:
    """Assert that the submitted repository URL is persisted in SQLite."""
    with sqlite3.connect(registration_context["database_path"]) as connection:
        row = connection.execute(
            """
            SELECT submitted_adapter_name, source_kind, repository_location
            FROM registration_sources
            """
        ).fetchone()

    assert row == (
        "Clinical Knowledge Adapter",
        "remote",
        "https://github.com/example/clinical-knowledge-adapter",
    )


@then("the submission receives a tracked registration status")
def submission_receives_status(registration_context: dict[str, Any]) -> None:
    """Assert that the stored submission reports a tracked status."""
    get_response = registration_context["get_response"]
    post_response = registration_context["post_response"]

    assert get_response[0][0] == 200
    assert "Register Adapter" in get_response[0][1]
    assert post_response[0][0] == 200
    assert "Registration request stored" in post_response[0][1]
    assert "SUBMITTED" in post_response[0][1]


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
