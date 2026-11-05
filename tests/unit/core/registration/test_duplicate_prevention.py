"""Duplicate protection and explicit recovery of historical unpublished sources."""

import json

import pytest

from src.core.auth.models import AuthSession
from src.core.registration.errors import DuplicateRegistrationError
from src.core.registration.models import AttemptStatus
from src.core.registration.service import register_adapter
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore
from tests.support.croissant_fixtures import sample_adapter_document
from tests.support.registration_fixtures import accepted_source, historical_source


@pytest.fixture
def repository(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    (path / "croissant.jsonld").write_text(json.dumps(sample_adapter_document()))
    return path


@pytest.mark.parametrize(
    "canonical, alias",
    [
        ("https://github.com/owner/repo", "https://github.com/owner/repo/tree/master"),
        (
            "https://gitlab.example.org/group/repo",
            "https://gitlab.example.org/group/repo/-/tree/master",
        ),
    ],
)
def test_register_rejects_main_master_repository_alias(
    tmp_path, monkeypatch, canonical, alias
):
    monkeypatch.setenv(
        "REGISTRY_ALLOWED_REPOSITORY_HOSTS", "github.com,gitlab.example.org"
    )
    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    accepted_source(store, canonical)
    with pytest.raises(DuplicateRegistrationError):
        register_adapter(alias, store, actor=AuthSession(github_user_id="123"))


def test_legacy_unpublished_source_original_owner_can_recover(repository, tmp_path):
    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    original = historical_source(store, str(repository))
    assert store.list_active_registrations() == []
    outcome = register_adapter(
        str(repository), store, actor=AuthSession(github_user_id="123")
    )
    assert outcome.attempt_status == AttemptStatus.SUCCEEDED
    assert outcome.registration.registration_id == original.registration_id
    assert len(store.list_active_registrations()) == 1
    assert [
        e.event_type for e in store.list_registration_events(original.registration_id)
    ] == ["VALID_CREATED"]


@pytest.mark.parametrize("owner", ["456", None, "0"])
def test_cannot_claim_legacy_source_owned_by_another_identity(
    repository, tmp_path, owner
):
    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    original = historical_source(store, str(repository), owner=owner)
    with pytest.raises(PermissionError):
        register_adapter(
            str(repository), store, actor=AuthSession(github_user_id="123")
        )
    assert (
        store.get_registration(original.registration_id).current_registry_entry_id
        is None
    )
    assert store.list_registration_events(original.registration_id) == []


def test_duplicate_canonical_identity_from_second_repository_is_not_saved(
    repository, tmp_path
):
    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    accepted_source(store, "https://github.com/owner/original")
    outcome = register_adapter(
        str(repository), store, actor=AuthSession(github_user_id="123")
    )
    assert outcome.attempt_status == AttemptStatus.FAILED
    assert store.get_registration_by_repository_location(str(repository)) is None
    assert len(store.list_registry_entries()) == 1


def test_acceptance_rejects_duplicate_uniqueness_key_transactionally(tmp_path):
    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    accepted_source(store, "https://github.com/owner/first")
    with pytest.raises(DuplicateRegistrationError):
        accepted_source(store, "https://github.com/owner/second")
    assert (
        store.get_registration_by_repository_location("https://github.com/owner/second")
        is None
    )
    assert len(store.list_registry_entries()) == 1


@pytest.mark.parametrize(
    "canonical, alias",
    [
        ("https://github.com/owner/repo", "https://github.com/owner/repo/tree/main"),
        (
            "https://gitlab.example.org/group/repo",
            "https://gitlab.example.org/group/repo/-/tree/main",
        ),
    ],
)
def test_legacy_recovery_normalizes_repository_alias(
    tmp_path, monkeypatch, canonical, alias
):
    from src.core.adapter.discovery import AdapterDiscoveryResult

    monkeypatch.setenv(
        "REGISTRY_ALLOWED_REPOSITORY_HOSTS", "github.com,gitlab.example.org"
    )
    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    legacy = historical_source(store, canonical)
    monkeypatch.setattr(
        "src.core.registration.service.discover_remote_adapter",
        lambda url: AdapterDiscoveryResult(
            source=url, metadata=sample_adapter_document()
        ),
    )
    outcome = register_adapter(alias, store, actor=AuthSession(github_user_id="123"))
    assert outcome.attempt_status == AttemptStatus.SUCCEEDED
    assert outcome.registration.registration_id == legacy.registration_id
    assert outcome.registration.repository_location == canonical
    assert len(store.list_active_registrations()) == 1


@pytest.mark.parametrize("operation", ["register", "update"])
def test_public_processing_requires_actor_before_store_access(operation):
    from unittest.mock import Mock

    from src.core.registration.service import update_adapter

    store = Mock()
    with pytest.raises(PermissionError):
        if operation == "register":
            register_adapter("https://github.com/owner/repo", store, actor=None)
        else:
            update_adapter("example-adapter", store, actor=None)
    assert store.mock_calls == []
