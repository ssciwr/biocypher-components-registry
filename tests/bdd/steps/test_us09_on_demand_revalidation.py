import json

import pytest
from pytest_bdd import given, scenarios, then, when

from src.core.auth.models import AuthSession
from src.core.registration.service import (
    latest_processing_outcome,
    register_adapter,
    update_adapter,
)
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore
from tests.support.croissant_fixtures import sample_adapter_document

scenarios("../features/us09_on_demand_revalidation.feature")


@pytest.fixture
def context(tmp_path):
    repository = tmp_path / "adapter"
    repository.mkdir()
    return {
        "repository": repository,
        "store": SQLiteRegistrationStore(tmp_path / "registry.sqlite3"),
    }


@given("a published adapter has a failed candidate update")
def failed(context):
    path = context["repository"] / "croissant.jsonld"
    path.write_text(json.dumps(sample_adapter_document()))
    first = register_adapter(
        str(context["repository"]), context["store"], actor=AuthSession("123")
    )
    assert first.attempt_status == "SUCCEEDED"
    context["first"] = first.registration
    metadata = sample_adapter_document()
    metadata["version"] = "1.1.0"
    metadata.pop("license")
    path.write_text(json.dumps(metadata))
    outcome = update_adapter(
        "example-adapter", context["store"], actor=AuthSession("123")
    )
    assert outcome.attempt_status == "FAILED"
    assert outcome.published_version == "1.0.0"
    context["metadata"] = metadata


@given("the maintainer corrects the candidate metadata")
def correct(context):
    context["metadata"]["license"] = sample_adapter_document()["license"]
    (context["repository"] / "croissant.jsonld").write_text(
        json.dumps(context["metadata"])
    )


@when("the same manual update action is repeated")
def retry(context):
    context["outcome"] = update_adapter(
        "example-adapter", context["store"], actor=AuthSession("123")
    )


@then("the corrected version is published immediately")
def published(context):
    assert context["outcome"].attempt_status == "SUCCEEDED"
    assert context["outcome"].published_version == "1.1.0"
    assert context["outcome"].update_applied


@then("the accepted metadata and update history are consistent")
def history(context):
    current = context["store"].get_registration(context["first"].registration_id)
    # MLCroissant enriches the JSON-LD context; all supplied mappings and
    # metadata values must still be present in the accepted document.
    for key, value in context["metadata"].items():
        if key == "@context":
            assert current.metadata[key].items() >= value.items()
        else:
            assert current.metadata[key] == value
    assert not hasattr(current, "status")
    assert (
        latest_processing_outcome(current, context["store"]).attempt_status
        == "SUCCEEDED"
    )
    events = context["store"].list_registration_events(current.registration_id)
    assert len(events) == 3
    assert events[0].event_type == events[-1].event_type == "VALID_CREATED"
    assert events[1].error_details
