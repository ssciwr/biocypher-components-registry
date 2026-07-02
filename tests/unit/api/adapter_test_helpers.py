from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.dependencies import get_optional_auth_session, get_registration_store
from src.core.auth.models import AuthSession
from src.core.registration.service import submit_registration
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore

"""
This file is fully AI-generated to save time and made tests easier to read/manage
"""

def create_adapter_entry(
    store: SQLiteRegistrationStore,
    repository: Path | None,
    *,
    adapter_id: str,
    adapter_name: str,
    version: str = "1.0.0",
    doi: str | None = None,
    cff_url: str | None = None,
    repository_location: str | None = None,
    submitted_by_github_login: str | None = None,
) -> None:
    """AI-Generated.

    Create one canonical registry entry for adapter API tests.
    """
    if repository_location is None:
        if repository is None:
            raise ValueError("Local repository path is required.")
        repository.mkdir()
        repository_location = str(repository)
    metadata_path = str(repository / "croissant.jsonld") if repository else None
    registration = submit_registration(
        adapter_name,
        repository_location,
        store,
        doi=doi,
        cff_url=cff_url,
        submitted_by_github_login=submitted_by_github_login,
    )
    store.mark_registration_valid(
        registration_id=registration.registration_id,
        metadata={"@id": adapter_id, "name": adapter_name, "version": version},
        metadata_path=metadata_path,
        profile_version="v1",
        uniqueness_key=f"{adapter_id}::{version}",
        observed_checksum=f"checksum-{adapter_id}",
    )


def create_adapter_client(
    store: SQLiteRegistrationStore,
    github_login: str | None = None,
) -> TestClient:
    """AI-Generated.

    Create an API test client with an overridden registration store.
    """
    app = create_app()
    app.dependency_overrides[get_registration_store] = lambda: store
    if github_login is not None:
        app.dependency_overrides[get_optional_auth_session] = lambda: AuthSession(
            github_login=github_login
        )
    return TestClient(app)
