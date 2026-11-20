import json

import pytest
from pytest_bdd import given, scenarios, then, when
from sqlalchemy import func, select

from src.core.auth.models import AuthSession
from src.core.registration.service import register_adapter, update_adapter
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore
from src.persistence.tables import (
    registration_events_table,
    registration_sources_table,
    registry_entries_table,
)
from tests.support.croissant_fixtures import sample_adapter_document

scenarios(
    "../features/us06a_registration_database_architecture_and_event_history.feature"
)


@pytest.fixture
def context(tmp_path):
    repository = tmp_path / "adapter"
    repository.mkdir()
    return {
        "repository": repository,
        "root": tmp_path,
        "store": SQLiteRegistrationStore(tmp_path / "registry.sqlite3"),
    }


def counts(context):
    with context["store"].engine.connect() as connection:
        return tuple(
            connection.scalar(select(func.count()).select_from(table))
            for table in (
                registration_sources_table,
                registry_entries_table,
                registration_events_table,
            )
        )


@given("a repository contains valid adapter metadata")
def valid(context):
    (context["repository"] / "croissant.jsonld").write_text(
        json.dumps(sample_adapter_document())
    )


@given("a repository contains invalid adapter metadata")
def invalid(context):
    metadata = sample_adapter_document()
    metadata.pop("license")
    (context["repository"] / "croissant.jsonld").write_text(json.dumps(metadata))


@when("architecture registration accepts the repository")
@when("architecture registration rejects the repository")
def register(context):
    context["outcome"] = register_adapter(
        str(context["repository"]), context["store"], actor=AuthSession("123")
    )


@given("an adapter has already been accepted")
def published(context):
    valid(context)
    register(context)
    assert context["outcome"].attempt_status == "SUCCEEDED"
    context["first"] = context["outcome"].registration


@then("one source and one success event are persisted together")
def atomic(context):
    assert context["outcome"].attempt_status == "SUCCEEDED"
    assert counts(context) == (1, 1, 1)
    events = context["store"].list_registration_events(
        context["outcome"].registration.registration_id
    )
    assert events[0].event_type == "VALID_CREATED"
    assert (
        events[0].registry_entry_id
        == context["outcome"].registration.current_registry_entry_id
    )


@then("the source points to the accepted canonical metadata")
def canonical(context):
    source = context["outcome"].registration
    entry = context["store"].get_registry_entry(source.current_registry_entry_id)
    assert entry.source_id == source.registration_id
    assert entry.metadata == source.metadata
    assert entry.metadata["hasPart"] == sample_adapter_document()["hasPart"]
    assert source.uniqueness_key == "example-adapter::1.0.0"
    assert counts(context) == (1, 1, 1)


@when("the published adapter is updated without metadata changes")
def unchanged(context):
    context["outcome"] = update_adapter(
        "example-adapter", context["store"], actor=AuthSession("123")
    )


@then("the canonical entry is unchanged and an UNCHANGED event is appended")
def same_entry(context):
    assert context["outcome"].attempt_status == "SUCCEEDED"
    assert not context["outcome"].update_applied
    assert (
        context["outcome"].registration.current_registry_entry_id
        == context["first"].current_registry_entry_id
    )
    assert counts(context) == (1, 1, 2)
    assert (
        context["store"].get_latest_event_type(context["first"].registration_id)
        == "UNCHANGED"
    )


@when("another repository submits the same adapter identity and version")
def duplicate(context):
    repository = context["root"] / "duplicate"
    repository.mkdir()
    (repository / "croissant.jsonld").write_text(json.dumps(sample_adapter_document()))
    context["outcome"] = register_adapter(
        str(repository), context["store"], actor=AuthSession("123")
    )
    context["duplicate"] = repository


@then("the duplicate is rejected without storing its source or failure event")
def duplicate_rejected(context):
    assert context["outcome"].reason_code == "DUPLICATE"
    assert context["outcome"].attempt_status == "FAILED"
    assert (
        context["store"].get_registration_by_repository_location(
            str(context["duplicate"])
        )
        is None
    )
    assert counts(context) == (1, 1, 1)


@then("there are no source, entry or attempt records")
def empty(context):
    assert context["outcome"].attempt_status == "FAILED"
    assert counts(context) == (0, 0, 0)
