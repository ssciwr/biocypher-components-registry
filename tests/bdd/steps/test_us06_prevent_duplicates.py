import json

import pytest
from pytest_bdd import given, scenarios, then, when

from src.core.auth.models import AuthSession
from src.core.registration.service import register_adapter
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore
from tests.support.croissant_fixtures import sample_adapter_document

scenarios("../features/us06_prevent_duplicates.feature")


@pytest.fixture
def context(tmp_path):
    return {
        "root": tmp_path,
        "store": SQLiteRegistrationStore(tmp_path / "registry.sqlite3"),
    }


def repository(context, name):
    path = context["root"] / name
    path.mkdir()
    (path / "croissant.jsonld").write_text(json.dumps(sample_adapter_document()))
    return str(path)


@given("an adapter is already stored with a uniqueness key")
def accepted(context):
    first = register_adapter(
        repository(context, "first"), context["store"], actor=AuthSession("123")
    )
    assert first.attempt_status == "SUCCEEDED"
    context["first"] = first.registration


@when("another registration uses the same uniqueness key")
def duplicate(context):
    context["outcome"] = register_adapter(
        repository(context, "second"), context["store"], actor=AuthSession("123")
    )


@then("the system rejects the new submission as duplicate")
def rejected(context):
    assert context["outcome"].attempt_status == "FAILED"
    assert context["outcome"].reason_code == "DUPLICATE"
    assert context["outcome"].registration is None
    assert len(context["store"].list_active_registrations()) == 1
    assert len(context["store"].list_registry_entries()) == 1
    assert (
        context["store"].get_registration(context["first"].registration_id).metadata
        == context["first"].metadata
    )
