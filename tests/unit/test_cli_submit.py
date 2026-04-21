from __future__ import annotations

import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from cli import app
from src.core.adapter.service import create_registration_request
from src.core.settings import settings as core_settings
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore


runner = CliRunner()


def test_submit_command_creates_local_registration_request(tmp_path: Path) -> None:
    """Create a registration request for a valid local repository submission."""
    repository = tmp_path / "adapter-repo"
    repository.mkdir()

    result = runner.invoke(
        app,
        [
            "submit",
            "--name",
            "Example Adapter",
            "--contact-email",
            "maintainer@example.org",
            str(repository),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Registration Request" in result.output
    assert "Registration request created" in result.output
    assert "example-adapter" in result.output
    assert "maintainer@example.org" in result.output
    assert "local" in result.output


def test_submit_command_rejects_missing_local_repository(tmp_path: Path) -> None:
    """Reject a local repository submission when the path does not exist."""
    repository = tmp_path / "missing-adapter-repo"

    result = runner.invoke(
        app,
        ["submit", "--name", "Example Adapter", str(repository)],
    )

    assert result.exit_code == 1
    assert "Repository path not found" in result.output


def test_submit_registration_command_persists_registration(tmp_path: Path) -> None:
    """Persist a registration through the CLI and return its stored identifier."""
    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    database_path = tmp_path / "registry.sqlite3"

    result = runner.invoke(
        app,
        [
            "submit-registration",
            "--name",
            "Example Adapter",
            "--contact-email",
            "maintainer@example.org",
            str(repository),
            "--db-path",
            str(database_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Stored Registration" in result.output
    assert "Registration stored" in result.output
    assert "maintainer@example.org" in result.output
    assert "SUBMITTED" in result.output

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT
                submitted_adapter_name,
                repository_location,
                source_kind,
                contact_email,
                is_active
            FROM registration_sources
            """
        ).fetchone()

        assert row == (
            "Example Adapter",
            str(repository.resolve()),
            "local",
            "maintainer@example.org",
            1,
        )


def test_submit_registration_command_uses_environment_database_path(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Persist a registration through the shared database path environment setting."""
    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    database_path = tmp_path / "registry.sqlite3"
    monkeypatch.setenv(core_settings.registry_db_path_env, str(database_path))

    result = runner.invoke(
        app,
        [
            "submit-registration",
            "--name",
            "Example Adapter",
            str(repository),
        ],
    )

    assert result.exit_code == 0, result.output
    assert database_path.exists()


def test_submit_registration_command_rejects_missing_local_repository(
    tmp_path: Path,
) -> None:
    """Reject a stored registration when the repository path does not exist."""
    database_path = tmp_path / "registry.sqlite3"
    repository = tmp_path / "missing-adapter-repo"

    result = runner.invoke(
        app,
        [
            "submit-registration",
            "--name",
            "Example Adapter",
            str(repository),
            "--db-path",
            str(database_path),
        ],
    )

    assert result.exit_code == 1
    assert "Repository path not found" in result.output


def test_list_registrations_command_shows_stored_registration(tmp_path: Path) -> None:
    """List stored registrations through the CLI."""
    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    database_path = tmp_path / "registry.sqlite3"
    runner.invoke(
        app,
        [
            "submit-registration",
            "--name",
            "Example Adapter",
            str(repository),
            "--db-path",
            str(database_path),
        ],
    )

    result = runner.invoke(
        app,
        ["list-registrations", "--db-path", str(database_path)],
    )

    assert result.exit_code == 0, result.output
    assert "Stored Registrations" in result.output
    assert "Example" in result.output
    assert "Adapter" in result.output
    assert "SUBMITTED" in result.output


def test_show_registration_events_command_shows_event_history(tmp_path: Path) -> None:
    """Show registration event history through the CLI."""
    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    database_path = tmp_path / "registry.sqlite3"
    store = SQLiteRegistrationStore(database_path)
    created = store.create_registration(
        create_registration_request(
            adapter_name="Example Adapter",
            repository_location=str(repository),
        )
    )

    result = runner.invoke(
        app,
        [
            "show-registration-events",
            created.registration_id,
            "--db-path",
            str(database_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Registration Events" in result.output
    assert "SUBMITTED" in result.output
    assert "Registration" in result.output
    assert "submitted" in result.output


def test_list_registry_entries_command_shows_canonical_entries(tmp_path: Path) -> None:
    """List active canonical registry entries through the CLI."""
    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    database_path = tmp_path / "registry.sqlite3"
    store = SQLiteRegistrationStore(database_path)
    created = store.create_registration(
        create_registration_request(
            adapter_name="Example Adapter",
            repository_location=str(repository),
        )
    )
    store.mark_registration_valid(
        registration_id=created.registration_id,
        metadata={"@id": "example-adapter", "name": "Example Adapter", "version": "1.0.0"},
        metadata_path=str(repository / "croissant.jsonld"),
        profile_version="v1",
        uniqueness_key="example-adapter::1.0.0",
        observed_checksum="checksum-1",
    )

    result = runner.invoke(
        app,
        ["list-registry-entries", "--db-path", str(database_path)],
    )

    assert result.exit_code == 0, result.output
    assert "Registry Entries" in result.output
    assert "Example" in result.output
    assert "Adapter" in result.output
    assert "1.0.0" in result.output
