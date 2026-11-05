"""Malformed JSON-LD produces terminal failures and retains update history."""

from copy import deepcopy
from unittest.mock import patch

import pytest

from src.core.adapter.discovery import AdapterDiscoveryResult
from src.core.auth.models import AuthSession
from src.core.registration.models import AttemptStatus
from src.core.registration.service import register_adapter, update_adapter
from tests.support.croissant_fixtures import sample_adapter_document


@pytest.mark.parametrize(
    "field,value",
    [
        ("@context", None),
        ("@context", []),
        ("@context", 3),
        ("@id", None),
        ("@id", []),
        ("@id", {}),
        ("@id", 3),
    ],
)
def test_bad_jsonld_is_retryable_and_failed_update_is_recorded(
    registration_store, field, value
):
    store = registration_store
    document = sample_adapter_document()
    document[field] = value
    with patch(
        "src.core.registration.service.discover_remote_adapter",
        side_effect=lambda url: AdapterDiscoveryResult(url, deepcopy(document)),
    ):
        failed = register_adapter(
            "https://github.com/owner/adapter", store, actor=AuthSession("123")
        )
        assert failed.attempt_status == AttemptStatus.FAILED
        assert failed.validation_errors
        assert store.list_registry_entries() == store.list_active_registrations() == []
        document = sample_adapter_document()
        accepted = register_adapter(
            "https://github.com/owner/adapter", store, actor=AuthSession("123")
        )
        document[field] = value
        document["version"] = "next"
        update = update_adapter("example-adapter", store, actor=AuthSession("123"))
    assert update.attempt_status == AttemptStatus.FAILED
    assert update.published_version == "1.0.0"
    assert update.registration.metadata == accepted.registration.metadata
    events = store.list_registration_events(accepted.registration.registration_id)
    assert len(events) == 2
    assert events[-1].error_details
