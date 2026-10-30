import json

import pytest
from pytest_bdd import given, scenarios, then, when
from sqlalchemy import func, select

from src.core.auth.models import AuthSession
from src.core.registration.service import register_adapter
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore
from src.persistence.tables import (
    registration_events_table,
    registration_sources_table,
    registry_entries_table,
)
from tests.support.croissant_fixtures import sample_adapter_document

scenarios("../features/us07_persist_invalid_status_and_errors.feature")


@pytest.fixture
def context(tmp_path):
    repository = tmp_path / "adapter"
    repository.mkdir()
    return {
        "repository": repository,
        "store": SQLiteRegistrationStore(tmp_path / "registry.sqlite3"),
    }


@given("an unregistered repository contains metadata missing a required version")
def invalid(context):
    metadata = sample_adapter_document()
    metadata.pop("version")
    (context["repository"] / "croissant.jsonld").write_text(json.dumps(metadata))


@when("invalid metadata is registered")
def register(context):
    context["outcome"] = register_adapter(
        str(context["repository"]), context["store"], actor=AuthSession("123")
    )


@then("the terminal attempt fails with version diagnostics")
def failed(context):
    outcome = context["outcome"]
    assert outcome.attempt_status == "FAILED"
    assert outcome.registration is None
    assert outcome.published_version is None
    assert any("version" in error for error in outcome.validation_errors)


@then("no source, canonical entry or failure event is saved")
def nothing_saved(context):
    with context["store"].engine.connect() as connection:
        for table in (
            registration_sources_table,
            registry_entries_table,
            registration_events_table,
        ):
            assert connection.scalar(select(func.count()).select_from(table)) == 0
