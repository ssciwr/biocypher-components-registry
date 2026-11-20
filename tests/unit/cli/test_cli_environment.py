"""Importing the CLI must not load application credentials into other callers."""

import subprocess
import sys

import cli


def test_importing_cli_does_not_load_dotenv():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from unittest.mock import patch; "
                "guard = patch('dotenv.load_dotenv', side_effect=AssertionError("
                "'Import must not load application configuration')); "
                "guard.start(); import cli"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


def test_cli_entry_point_loads_environment_before_running_commands(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "load_dotenv", lambda: calls.append("configuration"))
    monkeypatch.setattr(cli, "app", lambda: calls.append("command"))
    cli.main()
    assert calls == ["configuration", "command"]


def test_maintenance_setup_failure_is_sanitized(monkeypatch, tmp_path):
    from typer.testing import CliRunner

    def fail(*args):
        raise OSError("private-database-password")

    monkeypatch.setattr("src.persistence.factory.SQLiteRegistrationStore", fail)
    result = CliRunner().invoke(
        cli.app,
        ["list-registrations", "--db-path", str(tmp_path / "unavailable.sqlite3")],
    )
    assert result.exit_code == 1
    assert "Database setup failed" in result.output
    assert "private-database-password" not in result.output
    assert "Traceback" not in result.output
