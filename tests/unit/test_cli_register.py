"""CLI registration exercises the real services/database without a registry API."""

from copy import deepcopy
from unittest.mock import Mock

import pytest
from sqlalchemy import func, select
from typer.testing import CliRunner

import cli
from src.core.adapter.discovery import AdapterDiscoveryResult
from src.core.auth.models import AuthSession
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore
from src.persistence.tables import (
    registration_events_table,
    registration_sources_table,
    registry_entries_table,
)
from tests.support.croissant_fixtures import sample_adapter_document

runner = CliRunner()
REPO = "https://github.com/example/example-adapter"


@pytest.fixture
def cli_environment(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_ID", "fixture-client")
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_SECRET", "fixture-secret")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    auth = Mock(return_value=AuthSession(github_user_id="123"))
    monkeypatch.setattr(cli, "authenticate_github_device", auth)
    return tmp_path / "registry.sqlite3", auth


def table_counts(store):
    with store.engine.connect() as connection:
        return tuple(
            connection.scalar(select(func.count()).select_from(table))
            for table in (
                registration_sources_table,
                registry_entries_table,
                registration_events_table,
            )
        )


def remote_document(monkeypatch, document):
    monkeypatch.setattr(
        "src.core.registration.service.discover_remote_adapter",
        lambda url: AdapterDiscoveryResult(source=url, metadata=deepcopy(document)),
    )


def test_register_publishes_as_verified_account(cli_environment, monkeypatch):
    path, auth = cli_environment
    remote_document(monkeypatch, sample_adapter_document())
    result = runner.invoke(cli.app, ["register", REPO, "--db-path", str(path)])
    assert result.exit_code == 0, result.output
    assert "SUCCEEDED" in result.output
    assert "1.0.0" in result.output
    auth.assert_called_once()
    store = SQLiteRegistrationStore(path)
    source = store.get_registration_by_repository_location(REPO)
    assert source.submitted_by_github_user_id == "123"
    assert source.current_registry_entry_id is not None
    assert not hasattr(source, "status")
    assert table_counts(store) == (1, 1, 1)
    assert not (path.parent / "config").exists()


def test_failed_registration_leaves_nothing_and_same_version_retry_succeeds(
    cli_environment, monkeypatch
):
    path, auth = cli_environment
    document = sample_adapter_document()
    document.pop("license")
    remote_document(monkeypatch, document)
    first = runner.invoke(cli.app, ["register", REPO, "--db-path", str(path)])
    assert first.exit_code == 1, first.output
    assert "FAILED" in first.output and "license" in first.output
    assert table_counts(SQLiteRegistrationStore(path)) == (0, 0, 0)
    remote_document(monkeypatch, sample_adapter_document())
    retry = runner.invoke(cli.app, ["register", REPO, "--db-path", str(path)])
    assert retry.exit_code == 0, retry.output
    assert "1.0.0" in retry.output
    assert auth.call_count == 2  # Authentication is fresh for every command.
    assert table_counts(SQLiteRegistrationStore(path)) == (1, 1, 1)


def test_authentication_failure_blocks_registry_processing(
    cli_environment, monkeypatch
):
    from src.core.auth.service import GitHubAuthenticationError

    path, auth = cli_environment
    auth.side_effect = GitHubAuthenticationError(
        "Token revocation could not be confirmed."
    )
    discover = Mock(side_effect=AssertionError("must not fetch repository"))
    monkeypatch.setattr(
        "src.core.registration.service.discover_remote_adapter", discover
    )
    result = runner.invoke(cli.app, ["register", REPO, "--db-path", str(path)])
    assert result.exit_code == 1
    assert "revocation" in result.output.lower()
    discover.assert_not_called()
    if path.exists():
        assert table_counts(SQLiteRegistrationStore(path)) == (0, 0, 0)


@pytest.mark.parametrize(
    "repository", ["http://github.com/example/adapter", "/tmp/local-adapter"]
)
def test_non_https_registration_rejected_before_authentication(
    cli_environment, repository
):
    path, auth = cli_environment
    result = runner.invoke(cli.app, ["register", repository, "--db-path", str(path)])
    assert result.exit_code == 2, result.output
    auth.assert_not_called()


def test_register_uses_configured_sqlite_path(cli_environment, monkeypatch):
    path, _ = cli_environment
    monkeypatch.setenv("BIOCYPHER_REGISTRY_DB_PATH", str(path))
    remote_document(monkeypatch, sample_adapter_document())
    result = runner.invoke(cli.app, ["register", REPO])
    assert result.exit_code == 0, result.output
    assert table_counts(SQLiteRegistrationStore(path)) == (1, 1, 1)


def test_duplicate_registration_reports_failure_without_second_attempt_record(
    cli_environment, monkeypatch
):
    path, _ = cli_environment
    remote_document(monkeypatch, sample_adapter_document())
    first = runner.invoke(cli.app, ["register", REPO, "--db-path", str(path)])
    assert first.exit_code == 0, first.output
    repeated = runner.invoke(cli.app, ["register", REPO, "--db-path", str(path)])
    assert repeated.exit_code == 1, repeated.output
    assert "already registered" in repeated.output.lower()
    assert table_counts(SQLiteRegistrationStore(path)) == (1, 1, 1)


@pytest.mark.parametrize(
    "command",
    [
        "submit",
        "submit-registration",
        "finish-registration",
        "revalidate-registration",
        "login",
        "logout",
        "web",
    ],
)
def test_removed_commands_are_not_available(command):
    result = runner.invoke(cli.app, [command])
    assert result.exit_code == 2
    assert "No such command" in result.output


def test_disabled_device_flow_is_explained_before_database_creation(
    cli_environment, monkeypatch
):
    from src.core.auth.service import authenticate_github_device

    path, _ = cli_environment
    transport = Mock()
    provider_response = Mock(status_code=400)
    provider_response.json.return_value = {
        "error": "device_flow_disabled",
        "error_description": "private-provider-content",
    }
    transport.post.return_value = provider_response

    def authorize(**kwargs):
        return authenticate_github_device(**kwargs, http=transport)

    monkeypatch.setattr(cli, "authenticate_github_device", authorize)
    result = runner.invoke(cli.app, ["register", REPO, "--db-path", str(path)])
    assert result.exit_code == 1, result.output
    assert "Enable Device Flow" in result.output
    assert "private-provider-content" not in result.output
    assert not path.exists()
    transport.get.assert_not_called()
    transport.delete.assert_not_called()


def test_database_connection_failure_happens_before_authentication(
    cli_environment, monkeypatch
):
    from src.persistence.errors import DatabaseSetupError

    path, auth = cli_environment

    def unavailable(*args):
        raise DatabaseSetupError(
            "Cannot connect to PostgreSQL; adapter processing did not start."
        )

    monkeypatch.setattr(cli, "check_database_connection", unavailable)
    result = runner.invoke(cli.app, ["register", REPO, "--db-path", str(path)])
    assert result.exit_code == 1
    assert "Cannot connect" in result.output
    assert "unconfirmed" not in result.output
    auth.assert_not_called()
    assert not path.exists()


def test_failed_publish_does_not_repeat_progress_or_primary_error(
    cli_environment, monkeypatch
):
    path, _ = cli_environment
    document = sample_adapter_document()
    document.pop("license")
    remote_document(monkeypatch, document)
    result = runner.invoke(cli.app, ["register", REPO, "--db-path", str(path)])
    assert result.exit_code == 1
    assert result.output.count("Adapter schema: FAILED") == 1
