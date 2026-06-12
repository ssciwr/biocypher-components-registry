"""Runtime settings for the FastAPI application."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from src.core.settings import settings as core_settings

load_dotenv()


@dataclass(frozen=True, slots=True)
class ApiSettings:
    """Configuration values used by the API delivery layer."""

    service_name: str = "biocypher-components-registry"
    app_title: str = "BioCypher Components Registry API"
    app_version: str = "0.2.0"
    api_v1_prefix: str = "/api/v1"
    registry_db_path_env: str = core_settings.registry_db_path_env
    default_registry_db_path: Path = core_settings.default_registry_db_path
    github_oauth_client_id_env: str = "GITHUB_OAUTH_CLIENT_ID"
    github_oauth_client_secret_env: str = "GITHUB_OAUTH_CLIENT_SECRET"
    auth_session_secret_env: str = "AUTH_SESSION_SECRET"
    frontend_base_url_env: str = "FRONTEND_BASE_URL"
    api_base_url_env: str = "VITE_API_BASE_URL"
    auth_session_cookie_name: str = "bcr_session"
    auth_state_cookie_name: str = "bcr_oauth_state"
    auth_return_to_cookie_name: str = "bcr_auth_return_to"
    auth_session_days: int = 7

    @property
    def github_oauth_client_id(self) -> str | None:
        """Return the configured GitHub OAuth client id."""
        return os.getenv(self.github_oauth_client_id_env)

    @property
    def github_oauth_client_secret(self) -> str | None:
        """Return the configured GitHub OAuth client secret."""
        return os.getenv(self.github_oauth_client_secret_env)

    @property
    def auth_session_secret(self) -> str | None:
        """Return the configured local session signing secret."""
        return os.getenv(self.auth_session_secret_env)

    @property
    def frontend_base_url(self) -> str:
        """Return the frontend base URL used after login."""
        return os.getenv(self.frontend_base_url_env, "http://localhost:5173")

    @property
    def api_base_url(self) -> str:
        """Return the public API base URL used by frontend and OAuth callbacks."""
        return os.getenv(self.api_base_url_env, "http://localhost:8000")

    @property
    def cors_origins(self) -> tuple[str, ...]:
        """Allow the configured local frontend origin."""
        frontend_url = self.frontend_base_url.rstrip("/")
        local_alias = (
            frontend_url.replace("localhost", "127.0.0.1")
            if "localhost" in frontend_url
            else frontend_url.replace("127.0.0.1", "localhost")
        )
        return tuple(dict.fromkeys((frontend_url, local_alias)))


settings = ApiSettings()
