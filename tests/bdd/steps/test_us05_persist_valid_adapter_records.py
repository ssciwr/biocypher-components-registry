import json

import pytest
from pytest_bdd import given, scenarios, then, when

from src.core.auth.models import AuthSession
from src.core.registration.service import register_adapter
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore
from tests.support.croissant_fixtures import sample_adapter_document

scenarios("../features/us05_persist_valid_adapter_records.feature")


@pytest.fixture
def context(tmp_path):
    repository = tmp_path / "adapter"
    repository.mkdir()
    return {
        "repository": repository,
        "store": SQLiteRegistrationStore(tmp_path / "registry.sqlite3"),
    }


@given("an unregistered repository contains valid adapter metadata")
def valid(context):
    (context["repository"] / "croissant.jsonld").write_text(
        json.dumps(sample_adapter_document())
    )
    assert (
        context["store"].get_registration_by_repository_location(
            str(context["repository"])
        )
        is None
    )


@when("the adapter is registered")
def register(context):
    context["outcome"] = register_adapter(
        str(context["repository"]), context["store"], actor=AuthSession("123")
    )


@then("its accepted metadata is persisted")
def persisted(context):
    outcome = context["outcome"]
    assert outcome.attempt_status == "SUCCEEDED"
    loaded = context["store"].get_registration(outcome.registration.registration_id)
    assert loaded.metadata == outcome.registration.metadata
    expected = sample_adapter_document()
    assert loaded.metadata["hasPart"] == expected["hasPart"]
    assert loaded.metadata["license"] == expected["license"]
    assert loaded.uniqueness_key == "example-adapter::1.0.0"
    assert loaded.current_registry_entry_id is not None
    assert loaded.profile_version == "v1"


@then("the published registration has a success event and no lifecycle status")
def terminal(context):
    registration = context["outcome"].registration
    assert not hasattr(registration, "status")
    assert [
        event.event_type
        for event in context["store"].list_registration_events(
            registration.registration_id
        )
    ] == ["VALID_CREATED"]
