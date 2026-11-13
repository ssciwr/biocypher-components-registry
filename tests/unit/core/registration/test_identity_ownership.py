"""Ownership is enforced atomically when adding sources to an adapter identity."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

import pytest

from src.core.adapter.discovery import AdapterDiscoveryResult
from src.core.auth.models import AuthSession
from src.core.registration.service import register_adapter, update_adapter
from tests.support.croissant_fixtures import sample_adapter_document
from tests.support.registration_fixtures import accepted_source


def register(store, repository, owner, version):
    document = sample_adapter_document()
    document["version"] = version
    with patch(
        "src.core.registration.service.discover_remote_adapter",
        return_value=AdapterDiscoveryResult(repository, document),
    ):
        return register_adapter(repository, store, actor=AuthSession(owner))


def test_other_account_cannot_add_version_to_existing_identity(registration_store):
    store = registration_store
    first = register(store, "https://github.com/first/repository", "123", "1.0.0")
    with pytest.raises(PermissionError, match="submitting"):
        register(store, "https://github.com/second/repository", "456", "2.0.0")
    assert (
        len(store.list_registry_entries())
        == len(store.list_active_registrations())
        == 1
    )
    assert (
        store.get_registration_by_repository_location(
            "https://github.com/second/repository"
        )
        is None
    )
    assert (
        store.get_registration(first.registration.registration_id).metadata["version"]
        == "1.0.0"
    )


def test_owner_can_add_source_and_update_shared_identity(registration_store):
    store = registration_store
    register(store, "https://github.com/owner/first", "123", "1.0.0")
    register(store, "https://github.com/owner/second", "123", "2.0.0")
    document = sample_adapter_document()
    document["version"] = "release-next"
    with patch(
        "src.core.registration.service.discover_remote_adapter",
        return_value=AdapterDiscoveryResult("repository", document),
    ):
        result = update_adapter("example-adapter", store, actor=AuthSession("123"))
    assert result.published_version == "release-next"


def test_concurrent_different_owners_cannot_claim_same_identity(registration_store):
    store = registration_store
    barrier = Barrier(2)

    def claim(index):
        barrier.wait(timeout=5)
        try:
            accepted_source(
                store,
                f"https://github.com/owner-{index}/repository",
                owner=str(index),
                metadata={"@id": "shared", "name": "Shared", "version": f"{index}.0.0"},
            )
            return "accepted"
        except PermissionError:
            return "denied"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(claim, [1, 2]))
    assert sorted(results) == ["accepted", "denied"]
    assert (
        len(store.list_registry_entries())
        == len(store.list_active_registrations())
        == 1
    )
