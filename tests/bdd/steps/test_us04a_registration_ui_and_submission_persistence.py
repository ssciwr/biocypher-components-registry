from unittest.mock import Mock

import pytest
from pytest_bdd import given, scenarios, then, when
from typer.testing import CliRunner

import cli
from src.core.adapter.discovery import AdapterDiscoveryResult
from src.core.auth.models import AuthSession
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore
from tests.support.croissant_fixtures import sample_adapter_document

scenarios("../features/us04a_registration_ui_and_submission_persistence.feature")


@pytest.fixture
def registration_context(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_ID", "fixture-client")
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_SECRET", "fixture-secret")
    return {
        "database_path": tmp_path / "registry.sqlite3",
        "repository": "https://github.com/example/adapter",
    }


@given("the maintainer has a repository with valid metadata")
def valid_repository(registration_context, monkeypatch):
    monkeypatch.setattr(
        cli, "authenticate_github_device", Mock(return_value=AuthSession("123"))
    )
    monkeypatch.setattr(
        "src.core.registration.service.discover_remote_adapter",
        lambda url: AdapterDiscoveryResult(
            source=url, metadata=sample_adapter_document()
        ),
    )


@when("the maintainer registers the repository from the CLI")
def register(registration_context):
    registration_context["result"] = CliRunner().invoke(
        cli.app,
        [
            "register",
            registration_context["repository"],
            "--db-path",
            str(registration_context["database_path"]),
        ],
    )


@then("the accepted adapter and verified owner are stored")
def accepted(registration_context):
    store = SQLiteRegistrationStore(registration_context["database_path"])
    source = store.get_registration_by_repository_location(
        registration_context["repository"]
    )
    assert source is not None
    assert source.adapter_name == "Example Adapter"
    assert source.submitted_by_github_user_id == "123"
    assert source.current_registry_entry_id is not None
    assert len(store.list_registry_entries()) == 1
    assert [
        event.event_type
        for event in store.list_registration_events(source.registration_id)
    ] == ["VALID_CREATED"]


@then("the CLI reports the terminal successful attempt")
def successful(registration_context):
    result = registration_context["result"]
    assert result.exit_code == 0, result.output
    assert "SUCCEEDED" in result.output
    assert "SUBMITTED" not in result.output
