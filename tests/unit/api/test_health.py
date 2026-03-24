from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.dependencies import get_registration_database_path
from src.api.settings import settings


# ===========================================================
# Health Endpoint Tests
# ===========================================================


def test_health_endpoint_returns_ok() -> None:
    """Health endpoint returns a lightweight service status response."""
    client = TestClient(create_app())

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": settings.service_name,
    }


def test_openapi_uses_configured_application_metadata() -> None:
    """OpenAPI metadata comes from centralized API settings."""
    schema = create_app().openapi()

    assert schema["info"]["title"] == settings.app_title
    assert schema["info"]["version"] == settings.app_version


def test_api_routes_use_configured_version_prefix() -> None:
    """The application mounts routers under the configured API prefix."""
    paths = create_app().openapi()["paths"]

    assert f"{settings.api_v1_prefix}/health" in paths


def test_registration_database_path_uses_default_setting(monkeypatch) -> None:
    """Default registration database path comes from centralized settings."""
    monkeypatch.delenv(settings.registry_db_path_env, raising=False)

    assert get_registration_database_path() == settings.default_registry_db_path


def test_registration_database_path_uses_environment_override(
    monkeypatch,
    tmp_path,
) -> None:
    """The registry database path can be overridden for deployment."""
    database_path = tmp_path / "registry.sqlite3"
    monkeypatch.setenv(settings.registry_db_path_env, str(database_path))

    assert get_registration_database_path() == database_path
