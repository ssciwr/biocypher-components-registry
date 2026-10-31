"""Batch processing covers mixed published-source outcomes without staging."""

import json

import pytest

from src.core.auth.models import AuthSession
from src.core.registration.service import (
    refresh_active_registrations,
    register_adapter,
    update_registration,
)
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore
from tests.support.croissant_fixtures import sample_adapter_document
from tests.support.registration_fixtures import accepted_source, historical_source


def test_batch_refresh_processes_only_published_sources_and_counts_outcomes(tmp_path):
    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    paths = {}
    for kind in ("unchanged", "updated", "schema", "version", "fetch"):
        repo = tmp_path / kind
        repo.mkdir()
        document = sample_adapter_document()
        document["@id"] = kind
        (repo / "croissant.jsonld").write_text(json.dumps(document))
        result = register_adapter(
            str(repo), store, actor=AuthSession(github_user_id="123")
        )
        assert result.registration is not None
        paths[kind] = repo
    legacy = tmp_path / "unpublished"
    legacy.mkdir()
    source = historical_source(store, str(legacy))
    for kind in ("updated", "schema", "version"):
        path = paths[kind] / "croissant.jsonld"
        document = json.loads(path.read_text())
        if kind == "updated":
            document["version"] = "2.0.0"
        elif kind == "schema":
            document.pop("license")
        else:
            document["description"] = "Changed without a new version"
        path.write_text(json.dumps(document))
    (paths["fetch"] / "croissant.jsonld").unlink()
    summary = refresh_active_registrations(store)
    assert summary.active_sources == summary.processed == 5
    assert summary.unchanged == 1
    assert summary.valid_created == 1
    assert summary.invalid == 1
    assert summary.rejected_same_version_changed == 1
    assert summary.fetch_failed == 1
    assert store.list_registration_events(source.registration_id) == []


def test_unknown_registration_update_is_an_explicit_error(tmp_path):
    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    with pytest.raises(ValueError, match="Registration not found"):
        update_registration("missing", store)


def test_batch_continues_after_unexpected_source_failure_and_saves_summary(
    tmp_path, monkeypatch
):
    from src.core.registration import service

    store = SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
    first = accepted_source(store, "https://github.com/owner/first")
    second = accepted_source(
        store,
        "https://github.com/owner/second",
        metadata={"@id": "second", "name": "Second", "version": "1.0.0"},
    )
    attempted = []

    def process(source_id, _store, **kwargs):
        attempted.append(source_id)
        if source_id == first.registration_id:
            raise RuntimeError("Unexpected per-source failure")
        from src.core.registration.models import AttemptStatus, ProcessingOutcome

        return ProcessingOutcome(
            attempt_status=AttemptStatus.SUCCEEDED,
            message="No changes found.",
            registration=second,
        )

    monkeypatch.setattr(service, "update_registration", process)
    summary = refresh_active_registrations(store)
    assert set(attempted) == {first.registration_id, second.registration_id}
    assert summary.processed == 2
    assert summary.internal_failed == summary.unchanged == 1
    record = store.get_latest_batch_refresh()
    assert record.processed == 2
    assert record.internal_failed == record.unchanged == 1
