"""Direct-service CLI updates preserve accepted metadata and enforce ownership."""

from sqlalchemy import update
from typer.testing import CliRunner

import cli
from src.core.auth.models import AuthSession
from src.core.registration.service import register_adapter
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore
from src.persistence.tables import registration_sources_table
from tests.support.croissant_fixtures import sample_adapter_document
from tests.unit.test_cli_register import (
    REPO,
    remote_document,
    table_counts,
)
from tests.unit.test_cli_register import cli_environment as cli_environment  # noqa: PLC0414 - expose the pytest fixture.

runner = CliRunner()


def seed(path, monkeypatch):
    remote_document(monkeypatch, sample_adapter_document())
    store = SQLiteRegistrationStore(path)
    outcome = register_adapter(REPO, store, actor=AuthSession(github_user_id="123"))
    assert outcome.registration is not None
    return store, outcome.registration


def test_cli_updates_published_adapter_by_public_id(cli_environment, monkeypatch):
    path, auth = cli_environment
    store, registration = seed(path, monkeypatch)
    document = sample_adapter_document()
    document["version"] = "2.0.0"
    remote_document(monkeypatch, document)
    result = runner.invoke(
        cli.app, ["update", "example-adapter", "--db-path", str(path)]
    )
    assert result.exit_code == 0, result.output
    assert "SUCCEEDED" in result.output and "2.0.0" in result.output
    auth.assert_called_once()
    accepted = store.get_registration(registration.registration_id)
    assert accepted.metadata["version"] == "2.0.0"


def test_failed_cli_update_retains_published_metadata_and_records_failure(
    cli_environment, monkeypatch
):
    path, _ = cli_environment
    store, registration = seed(path, monkeypatch)
    document = sample_adapter_document()
    document.pop("license")
    remote_document(monkeypatch, document)
    result = runner.invoke(
        cli.app, ["update", "example-adapter", "--db-path", str(path)]
    )
    assert result.exit_code == 1, result.output
    assert "FAILED" in result.output and "license" in result.output
    assert "1.0.0" in result.output
    accepted = store.get_registration(registration.registration_id)
    assert accepted.metadata == registration.metadata
    assert table_counts(store) == (1, 1, 2)


def test_unchanged_cli_update_succeeds(cli_environment, monkeypatch):
    path, _ = cli_environment
    store, _ = seed(path, monkeypatch)
    result = runner.invoke(
        cli.app, ["update", "example-adapter", "--db-path", str(path)]
    )
    assert result.exit_code == 0, result.output
    assert "SUCCEEDED" in result.output
    assert table_counts(store) == (1, 1, 2)


def test_different_verified_account_cannot_update(cli_environment, monkeypatch):
    path, auth = cli_environment
    store, _ = seed(path, monkeypatch)
    auth.return_value = AuthSession(github_user_id="456")
    before = table_counts(store)
    result = runner.invoke(
        cli.app, ["update", "example-adapter", "--db-path", str(path)]
    )
    assert result.exit_code == 1, result.output
    assert table_counts(store) == before


def test_shared_update_rejects_adapter_if_any_source_has_another_owner(
    cli_environment, monkeypatch
):
    import pytest

    from src.core.registration.service import update_adapter

    path, _ = cli_environment
    store, first = seed(path, monkeypatch)
    second_document = sample_adapter_document()
    second_document["version"] = "2.0.0"
    remote_document(monkeypatch, second_document)
    register_adapter(
        "https://github.com/example/second-source",
        store,
        actor=AuthSession(github_user_id="123"),
    )
    with store.engine.begin() as connection:
        connection.execute(
            update(registration_sources_table)
            .where(registration_sources_table.c.id == first.registration_id)
            .values(submitted_by_github_user_id="456")
        )
    before = table_counts(store)
    with pytest.raises(PermissionError):
        update_adapter(
            "example-adapter", store, actor=AuthSession(github_user_id="123")
        )
    assert table_counts(store) == before


def test_force_validation_rechecks_unchanged_metadata(cli_environment, monkeypatch):
    from unittest.mock import Mock

    from src.core.registration import service

    path, _ = cli_environment
    store, first = seed(path, monkeypatch)
    validate = Mock(wraps=service.validate_discovered_adapter)
    monkeypatch.setattr(service, "validate_discovered_adapter", validate)
    result = runner.invoke(
        cli.app,
        ["update", first.adapter_id, "--force-validation", "--db-path", str(path)],
    )
    assert result.exit_code == 0, result.output
    validate.assert_called_once()
    assert len(store.list_registry_entries()) == 1
    assert len(store.list_registration_events(first.registration_id)) == 2
