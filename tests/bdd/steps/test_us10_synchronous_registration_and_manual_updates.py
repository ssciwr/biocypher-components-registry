from __future__ import annotations

import json

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.core.registration.service import (
    latest_processing_outcome,
    register_adapter,
    update_registration,
)
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore
from tests.support.croissant_fixtures import sample_adapter_document

scenarios("../features/us10_synchronous_registration_and_manual_updates.feature")


@pytest.fixture
def context(tmp_path):
    repository = tmp_path / "adapter"
    repository.mkdir()
    return {
        "repository": repository,
        "store": SQLiteRegistrationStore(tmp_path / "registry.sqlite3"),
    }


def write_metadata(context, *, invalid=False, changed=False):
    document = sample_adapter_document()
    if invalid:
        document.pop("license")
    if changed:
        document["description"] = "Changed metadata"
    (context["repository"] / "croissant.jsonld").write_text(json.dumps(document))


@given("an unregistered repository contains invalid metadata")
def invalid_repository(context):
    write_metadata(context, invalid=True)


@when("the repository is registered synchronously")
def register(context):
    context["outcome"] = register_adapter(str(context["repository"]), context["store"])


@given("its first synchronous registration failed")
def first_failed(context):
    register(context)
    assert context["outcome"].attempt_status == "FAILED"


@when("the metadata is corrected without changing its version")
def correct_metadata(context):
    write_metadata(context)


@then(parsers.parse("the attempt outcome is {status}"))
def outcome_status(context, status):
    assert context["outcome"].attempt_status == status


@then("no registration source, entry, or attempt event is stored")
def no_registration_records(context):
    from sqlalchemy import func, select

    from src.persistence.tables import (
        registration_events_table,
        registration_sources_table,
        registry_entries_table,
    )

    with context["store"].engine.connect() as connection:
        for table in (
            registration_sources_table,
            registry_entries_table,
            registration_events_table,
        ):
            assert connection.scalar(select(func.count()).select_from(table)) == 0


@then("one accepted registration and one success event are stored")
def accepted_registration(context):
    store = context["store"]
    assert len(store.list_active_registrations()) == 1
    assert len(store.list_registry_entries()) == 1
    assert [
        event.event_type
        for event in store.list_registration_events(
            context["outcome"].registration.registration_id
        )
    ] == ["VALID_CREATED"]


@given("an adapter has an accepted version")
def published_adapter(context):
    write_metadata(context)
    register(context)
    context["published"] = context["outcome"].registration


@when("its changed metadata is updated without bumping the version")
def update_without_version_change(context):
    write_metadata(context, changed=True)
    context["outcome"] = update_registration(
        context["published"].registration_id, context["store"]
    )


@then("the published metadata remains accepted")
def published_metadata_retained(context):
    current = context["store"].get_registration(context["published"].registration_id)
    assert current.status == "VALID"
    assert current.metadata == context["published"].metadata
    assert (
        current.current_registry_entry_id
        == context["published"].current_registry_entry_id
    )


@then("the update failure is available after reloading")
def failure_retained(context):
    store = context["store"]
    current = store.get_registration(context["published"].registration_id)
    outcome = latest_processing_outcome(current, store)
    assert outcome.attempt_status == "FAILED"
    assert outcome.reason_code == "VERSION_NOT_BUMPED"
    assert outcome.published_version == "1.0.0"
