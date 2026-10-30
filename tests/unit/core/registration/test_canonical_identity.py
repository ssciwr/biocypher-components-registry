"""Optional JSON-LD ids must not create random or inconsistent catalog identities."""

from copy import deepcopy
from unittest.mock import patch

import pytest

from src.core.adapter.discovery import AdapterDiscoveryResult
from src.core.auth.models import AuthSession
from src.core.registration.errors import DuplicateRegistrationError
from src.core.registration.service import register_adapter, update_adapter
from tests.support.croissant_fixtures import sample_adapter_document


def test_metadata_without_id_has_one_stable_identity_through_update(registration_store):
    document = sample_adapter_document()
    document.pop("@id")
    store = registration_store
    with patch(
        "src.core.registration.service.discover_remote_adapter",
        side_effect=lambda url: AdapterDiscoveryResult(url, deepcopy(document)),
    ):
        first = register_adapter(
            "https://github.com/owner/first", store, actor=AuthSession("123")
        )
        assert first.registration.adapter_id == "example-adapter"
        assert first.registration.uniqueness_key == "example-adapter::1.0.0"
        with pytest.raises(DuplicateRegistrationError):
            register_adapter(
                "https://github.com/owner/first", store, actor=AuthSession("123")
            )
        document["version"] = "next-release"
        result = update_adapter(
            first.registration.adapter_id, store, actor=AuthSession("123")
        )
        assert result.registration.adapter_id == first.registration.adapter_id
        assert result.published_version == "next-release"
    identities = {
        entry.uniqueness_key.split("::")[0] for entry in store.list_registry_entries()
    }
    assert identities == {first.registration.adapter_id}
