import json

import pytest
from pytest_bdd import given, scenarios, then, when

from src.core.auth.models import AuthSession
from src.core.registration.service import (
    refresh_active_registrations,
    register_adapter,
    update_adapter,
)
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore
from tests.support.croissant_fixtures import sample_adapter_document

scenarios("../features/us08_non_blocking_batch_registration.feature")


@pytest.fixture
def context(tmp_path):
    return {
        "root": tmp_path,
        "store": SQLiteRegistrationStore(tmp_path / "registry.sqlite3"),
        "sources": [],
    }


def publish(context, identifier):
    repository = context["root"] / identifier
    repository.mkdir()
    metadata = sample_adapter_document()
    metadata["@id"] = identifier
    (repository / "croissant.jsonld").write_text(json.dumps(metadata))
    result = register_adapter(
        str(repository), context["store"], actor=AuthSession("123")
    )
    assert result.attempt_status == "SUCCEEDED"
    context["sources"].append(result.registration)
    return repository, metadata, result.registration


@given("published sources include unchanged and invalid update candidates")
def mixed(context):
    publish(context, "unchanged")
    repository, metadata, source = publish(context, "invalid-update")
    metadata.pop("license")
    (repository / "croissant.jsonld").write_text(json.dumps(metadata))
    context["failed_source"] = source


@given("one published source cannot be fetched and another is unchanged")
def unavailable(context):
    publish(context, "unchanged")
    repository, _, source = publish(context, "missing")
    (repository / "croissant.jsonld").unlink()
    context["failed_source"] = source


@given("a published source has a failed update")
def failed_update(context):
    repository, metadata, source = publish(context, "corrected")
    metadata["version"] = "1.1.0"
    metadata.pop("license")
    (repository / "croissant.jsonld").write_text(json.dumps(metadata))
    outcome = update_adapter("corrected", context["store"], actor=AuthSession("123"))
    assert outcome.attempt_status == "FAILED"
    context.update(repository=repository, metadata=metadata, failed_source=source)


@given("its metadata is corrected before the next batch run")
def correct(context):
    context["metadata"]["license"] = sample_adapter_document()["license"]
    (context["repository"] / "croissant.jsonld").write_text(
        json.dumps(context["metadata"])
    )


@when("the batch update workflow runs")
def refresh(context):
    context["summary"] = refresh_active_registrations(context["store"])


@then("all published sources are processed")
def processed(context):
    assert context["summary"].processed == 2
    assert context["summary"].active_sources == 2
    assert len(context["store"].list_registry_entries()) == 2
    assert context["store"].get_latest_batch_refresh().processed == 2


@then("the batch reports the unchanged and invalid outcomes")
def mixed_outcomes(context):
    assert context["summary"].unchanged == 1
    assert context["summary"].invalid == 1
    current = context["store"].get_registration(
        context["failed_source"].registration_id
    )
    assert current.metadata == context["failed_source"].metadata


@then("the fetch failure is recorded while accepted metadata is retained")
def fetch_failure(context):
    assert context["summary"].fetch_failed == 1
    assert context["summary"].unchanged == 1
    source = context["failed_source"]
    assert (
        context["store"].get_registration(source.registration_id).metadata
        == source.metadata
    )
    events = context["store"].list_registration_events(source.registration_id)
    assert len(events) == 2
    assert events[-1].event_type == "METADATA_NOT_FOUND"


@then("the corrected version is published")
def corrected(context):
    assert context["summary"].processed == 1
    assert context["summary"].valid_created == 1
    current = context["store"].get_registration(
        context["failed_source"].registration_id
    )
    assert current.metadata["version"] == "1.1.0"
    assert len(context["store"].list_registry_entries()) == 2


@then("a VALID_CREATED outcome is recorded for the corrected version")
def success_recorded(context):
    assert (
        context["store"].get_latest_event_type(context["failed_source"].registration_id)
        == "VALID_CREATED"
    )
