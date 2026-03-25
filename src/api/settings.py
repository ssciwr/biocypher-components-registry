"""Runtime settings for the FastAPI application."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.core.settings import settings as core_settings


@dataclass(frozen=True, slots=True)
class ApiSettings:
    """Configuration values used by the API delivery layer."""

    service_name: str = "biocypher-components-registry"
    app_title: str = "BioCypher Components Registry API"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    registry_db_path_env: str = core_settings.registry_db_path_env
    default_registry_db_path: Path = core_settings.default_registry_db_path


settings = ApiSettings()
