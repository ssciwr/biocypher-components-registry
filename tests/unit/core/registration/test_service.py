from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from src.core.registration.models import RegistrationStatus, StoredRegistration
from src.core.registration.service import _build_uniqueness_key, submit_registration
from src.core.registration.store import RegistrationStore
from src.core.adapter.request import AdapterRegistrationRequest


class MemoryRegistrationStore:
    """Simple in-memory registration store for service tests."""

    def __init__(self) -> None:
        self.saved: list[StoredRegistration] = []

    def create_registration(
        self,
        request: AdapterRegistrationRequest,
    ) -> StoredRegistration:
        stored = StoredRegistration(
            registration_id="reg-1",
            adapter_name=request.adapter_name,
            adapter_id=request.adapter_id,
            repository_location=request.repository_location,
            repository_kind=request.repository_kind,
            status=RegistrationStatus.SUBMITTED,
            created_at=datetime.now(UTC),
            contact_email=request.contact_email,
        )
        self.saved.append(stored)
        return stored

    def get_registration(self, registration_id: str) -> StoredRegistration | None:
        for registration in self.saved:
            if registration.registration_id == registration_id:
                return registration
        return None

    def mark_registration_valid(self, *args: object, **kwargs: object) -> StoredRegistration:
        raise NotImplementedError

    def mark_registration_invalid(
        self,
        *args: object,
        **kwargs: object,
    ) -> StoredRegistration:
        raise NotImplementedError


def test_submit_registration_persists_created_request(tmp_path: Path) -> None:
    """Submit a registration through the service and store it."""
    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    store: RegistrationStore = MemoryRegistrationStore()

    stored = submit_registration(
        adapter_name="Example Adapter",
        repository_location=str(repository),
        store=store,
        contact_email="maintainer@example.org",
    )

    assert stored.adapter_name == "Example Adapter"
    assert stored.adapter_id == "example-adapter"
    assert stored.repository_kind == "local"
    assert stored.status == RegistrationStatus.SUBMITTED
    assert stored.contact_email == "maintainer@example.org"


def test_build_uniqueness_key_prefers_metadata_adapter_id_over_submitted_name() -> None:
    """Use the metadata adapter id as the canonical uniqueness key source."""
    uniqueness_key = _build_uniqueness_key(
        {
            "@id": "example-adapter",
            "name": "Example Adapter",
            "version": "1.0.0",
        },
        fallback_adapter_id="example-adapter-duplicate",
    )

    assert uniqueness_key == "example-adapter::1.0.0"
