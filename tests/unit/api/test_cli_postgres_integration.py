"""CLI and API share publication and ownership behavior on Docker PostgreSQL."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

from fastapi.testclient import TestClient
from typer.testing import CliRunner

import cli
from src.api.app import create_app
from src.core.adapter.discovery import AdapterDiscoveryResult
from src.core.auth.models import AuthSession
from src.persistence.factory import build_auth_session_store, build_registration_store
from tests.support.croissant_fixtures import sample_adapter_document


def test_cli_and_api_share_docker_postgres_publication_and_ownership(
    postgres_schema_url, monkeypatch
):
    monkeypatch.setenv("DATABASE_URL", postgres_schema_url)
    document = sample_adapter_document()
    document.pop("@id")
    monkeypatch.setattr(cli, "_authorize_cli", Mock(return_value=AuthSession("123")))
    monkeypatch.setattr(
        "src.core.registration.service.discover_remote_adapter",
        lambda url: AdapterDiscoveryResult(url, deepcopy(document)),
    )
    runner = CliRunner()
    result = runner.invoke(cli.app, ["register", "https://github.com/owner/adapter"])
    assert result.exit_code == 0, result.output
    assert "PostgreSQL" in result.output
    client = TestClient(create_app())
    assert client.get("/api/v1/adapters/example-adapter").json()["version"] == "1.0.0"
    sessions = build_auth_session_store()
    cookie = sessions.create_session(
        github_user_id="123", expires_at=datetime.now(UTC) + timedelta(hours=1)
    )
    client.cookies.set("bcr_session", cookie)
    document.pop("license")
    failed = client.post("/api/v1/adapters/example-adapter/update")
    assert failed.status_code == 200
    assert failed.json()["attempt_status"] == "FAILED"
    assert failed.json()["published_version"] == "1.0.0"
    document = sample_adapter_document()
    document.pop("@id")
    document["version"] = "release-next"
    updated = runner.invoke(cli.app, ["update", "example-adapter"])
    assert updated.exit_code == 0, updated.output
    assert (
        client.get("/api/v1/adapters/example-adapter").json()["version"]
        == "release-next"
    )
    other_cookie = sessions.create_session(
        github_user_id="456", expires_at=datetime.now(UTC) + timedelta(hours=1)
    )
    client.cookies.set("bcr_session", other_cookie)
    document["version"] = "other-release"
    rejected = client.post(
        "/api/v1/registrations",
        json={"repository_location": "https://github.com/another/adapter"},
    )
    assert rejected.status_code == 403
    assert len(build_registration_store().list_active_registrations()) == 1
    assert client.post("/api/v1/registry/refreshes").status_code == 404
