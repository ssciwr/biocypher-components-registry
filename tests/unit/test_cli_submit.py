"""Maintenance commands remain in the same CLI using accepted registrations."""

from typer.testing import CliRunner

from cli import app
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore
from tests.support.registration_fixtures import accepted_source, historical_source

runner = CliRunner()


def test_list_registrations_command_shows_only_published_registration(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    path = tmp_path / "registry.sqlite3"
    store = SQLiteRegistrationStore(path)
    accepted_source(store, "https://github.com/owner/published")
    historical_source(store, "https://github.com/owner/legacy")
    result = runner.invoke(app, ["list-registrations", "--db-path", str(path)])
    assert result.exit_code == 0, result.output
    assert "Stored Registrations" in result.output
    assert "Example" in result.output and "Adapter" in result.output
    assert "SUBMITTED" not in result.output
    assert "legacy" not in result.output


def test_show_registration_events_command_shows_accepted_history(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    path = tmp_path / "registry.sqlite3"
    store = SQLiteRegistrationStore(path)
    source = accepted_source(store, "https://github.com/owner/repo")
    result = runner.invoke(
        app,
        ["show-registration-events", source.registration_id, "--db-path", str(path)],
    )
    assert result.exit_code == 0, result.output
    assert "Registration Events" in result.output
    assert "VALID_CREATED" in result.output
    assert "SUBMITTED" not in result.output


def test_list_registry_entries_command_shows_canonical_entries(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    path = tmp_path / "registry.sqlite3"
    accepted_source(SQLiteRegistrationStore(path), "https://github.com/owner/repo")
    result = runner.invoke(app, ["list-registry-entries", "--db-path", str(path)])
    assert result.exit_code == 0, result.output
    assert "Registry Entries" in result.output
    assert "Example" in result.output and "Adapter" in result.output
    assert "1.0.0" in result.output


def test_seed_demo_adapters_command_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from unittest.mock import Mock

    from src.core.auth.models import AuthSession

    authorize = Mock(return_value=AuthSession("123"))
    monkeypatch.setattr("cli._authorize_cli", authorize)
    path = tmp_path / "registry.sqlite3"
    first = runner.invoke(app, ["seed-demo-adapters", "--db-path", str(path)])
    second = runner.invoke(app, ["seed-demo-adapters", "--db-path", str(path)])
    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert "Seeded 3 demo adapters" in first.output
    assert "skipped 3 existing" in second.output
    store = SQLiteRegistrationStore(path)
    assert len(store.list_registry_entries()) == 3
    assert {
        source.submitted_by_github_user_id
        for source in store.list_active_registrations()
    } == {"123"}
    assert authorize.call_count == 2
