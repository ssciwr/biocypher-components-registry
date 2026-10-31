"""Acceptance and rollback tests for the shared synchronous processor."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url

from src.core.auth.models import AuthSession
from src.core.registration.errors import (
    ConcurrentRegistrationChangeError,
    DuplicateRegistrationError,
)
from src.core.registration.models import AttemptStatus
from src.core.registration.service import (
    latest_processing_outcome,
    register_adapter,
    update_registration,
)
from src.core.shared.errors import RepositoryUnavailableError
from src.core.validation.results import (
    ValidationCheck,
    ValidationDetail,
    ValidationResult,
)
from src.persistence.registration_postgres_store import PostgreSQLRegistrationStore
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore
from src.persistence.tables import (
    registration_events_table,
    registration_sources_table,
    registry_entries_table,
)
from tests.support.croissant_fixtures import sample_adapter_document


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    repo = tmp_path / "adapter"
    repo.mkdir()
    (repo / "croissant.jsonld").write_text(json.dumps(sample_adapter_document()))
    return repo


@pytest.fixture(params=["sqlite", "postgres"])
def store(tmp_path: Path, request):
    if request.param == "sqlite":
        yield SQLiteRegistrationStore(tmp_path / "registry.sqlite3")
        return
    url = request.getfixturevalue("postgres_test_url")
    # Each case owns a fresh schema; never clear an existing database's tables.
    schema = f"registry_test_{uuid4().hex}"
    admin = create_engine(url)
    backend = None
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        isolated = make_url(url).update_query_dict(
            {"options": f"-csearch_path={schema}"}
        )
        backend = PostgreSQLRegistrationStore(
            isolated.render_as_string(hide_password=False)
        )
        yield backend
    finally:
        if backend is not None:
            backend.engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def counts(store: SQLiteRegistrationStore) -> tuple[int, ...]:
    with store.engine.connect() as connection:
        return tuple(
            connection.scalar(select(func.count()).select_from(table))
            for table in (
                registration_sources_table,
                registry_entries_table,
                registration_events_table,
            )
        )


@pytest.mark.parametrize(
    "failure, reason",
    [
        ("missing", "METADATA_NOT_FOUND"),
        ("json", "INVALID_JSON"),
        ("array", "INVALID_JSON"),
        ("schema", "SCHEMA_INVALID"),
        ("unavailable", "REMOTE_TEMPORARY"),
    ],
)
def test_failed_first_registration_writes_nothing(
    repository, store, monkeypatch, failure, reason
):
    """A failed first attempt has neither a persisted source nor an event."""
    path = repository / "croissant.jsonld"
    if failure == "missing":
        path.unlink()
    elif failure == "json":
        path.write_text("{")
    elif failure == "array":
        path.write_text("[]")
    elif failure == "schema":
        document = sample_adapter_document()
        document.pop("license")
        path.write_text(json.dumps(document))
    else:

        def unavailable(*args):
            raise RepositoryUnavailableError(
                "Host temporarily unavailable.", "REMOTE_TEMPORARY"
            )

        monkeypatch.setattr(
            "src.core.registration.service._discover_registration_metadata", unavailable
        )
    outcome = register_adapter(
        str(repository), store, actor=AuthSession(github_user_id="123")
    )
    assert outcome.attempt_status == AttemptStatus.FAILED
    assert outcome.reason_code == reason
    assert outcome.registration is None
    assert outcome.published_version is None
    assert counts(store) == (0, 0, 0)


def test_first_success_commits_all_records_and_retry_can_keep_version(
    repository, store
):
    path = repository / "croissant.jsonld"
    path.write_text("{")
    assert (
        register_adapter(
            str(repository), store, actor=AuthSession(github_user_id="123")
        ).attempt_status
        == AttemptStatus.FAILED
    )
    path.write_text(json.dumps(sample_adapter_document()))
    outcome = register_adapter(
        str(repository), store, actor=AuthSession(github_user_id="123")
    )
    assert outcome.attempt_status == AttemptStatus.SUCCEEDED
    assert outcome.published_version == "1.0.0"
    assert outcome.registration.adapter_name == "Example Adapter"
    assert outcome.registration.submitted_by_github_user_id == "123"
    assert counts(store) == (1, 1, 1)
    assert (
        store.get_latest_event_type(outcome.registration.registration_id)
        == "VALID_CREATED"
    )


def test_first_persistence_failure_rolls_back_source_and_entry(
    repository, store, monkeypatch
):
    def fail_event(*args, **kwargs):
        raise RuntimeError("event insert failed")

    monkeypatch.setattr(store, "_insert_registration_event", fail_event)
    with pytest.raises(RuntimeError, match="event insert failed"):
        register_adapter(
            str(repository), store, actor=AuthSession(github_user_id="123")
        )
    assert counts(store) == (0, 0, 0)


def test_duplicate_repository_does_not_create_another_attempt(repository, store):
    register_adapter(str(repository), store, actor=AuthSession(github_user_id="123"))
    before = counts(store)
    with pytest.raises(DuplicateRegistrationError):
        register_adapter(
            str(repository), store, actor=AuthSession(github_user_id="123")
        )
    assert counts(store) == before


@pytest.mark.parametrize(
    "failure, reason",
    [
        ("missing", "METADATA_NOT_FOUND"),
        ("json", "INVALID_JSON"),
        ("version", "VERSION_NOT_BUMPED"),
        ("schema", "SCHEMA_INVALID"),
        ("identity", "ADAPTER_ID_CHANGED"),
    ],
)
def test_failed_update_records_attempt_and_preserves_published_metadata(
    repository, store, failure, reason
):
    first = register_adapter(
        str(repository), store, actor=AuthSession(github_user_id="123")
    ).registration
    path = repository / "croissant.jsonld"
    document = sample_adapter_document()
    if failure == "missing":
        path.unlink()
    elif failure == "json":
        path.write_text("{")
    else:
        document["description"] = "Updated description"
        if failure != "version":
            document["version"] = "1.1.0"
        if failure == "schema":
            document.pop("license")
        if failure == "identity":
            document["@id"] = "different-adapter"
        path.write_text(json.dumps(document))
    outcome = update_registration(first.registration_id, store)
    assert outcome.attempt_status == AttemptStatus.FAILED
    assert outcome.reason_code == reason
    assert outcome.published_version == "1.0.0"
    assert not outcome.update_applied
    stored = store.get_registration(first.registration_id)
    assert stored.current_registry_entry_id is not None
    assert stored.current_registry_entry_id == first.current_registry_entry_id
    assert stored.metadata == first.metadata
    assert counts(store) == (1, 1, 2)
    latest = latest_processing_outcome(stored, store)
    assert latest.attempt_status == AttemptStatus.FAILED
    assert latest.reason_code == reason
    assert "Previous metadata retained" in latest.message


def test_update_accepts_new_version_and_unchanged_is_a_success(repository, store):
    first = register_adapter(
        str(repository), store, actor=AuthSession(github_user_id="123")
    ).registration
    document = sample_adapter_document()
    document.update(version="1.1.0", description="Updated description")
    (repository / "croissant.jsonld").write_text(json.dumps(document))
    updated = update_registration(first.registration_id, store)
    assert updated.attempt_status == AttemptStatus.SUCCEEDED
    assert updated.update_applied
    assert updated.published_version == "1.1.0"
    assert updated.message == "Updated from 1.0.0 to 1.1.0."
    assert (
        latest_processing_outcome(updated.registration, store).message
        == updated.message
    )
    unchanged = update_registration(first.registration_id, store)
    assert unchanged.attempt_status == AttemptStatus.SUCCEEDED
    assert not unchanged.update_applied
    assert unchanged.message == "No changes found."
    assert counts(store) == (1, 2, 3)


@pytest.mark.parametrize("force_validation", [False, True])
def test_unchanged_update_revalidates_only_when_forced(
    repository, store, monkeypatch, force_validation
):
    from src.core.registration import service

    first = register_adapter(
        str(repository), store, actor=AuthSession(github_user_id="123")
    ).registration
    validate = service.validate_discovered_adapter
    validated = []

    def track_validation(candidate, **kwargs):
        validated.append(candidate)
        return validate(candidate, **kwargs)

    monkeypatch.setattr(service, "validate_discovered_adapter", track_validation)
    outcome = update_registration(
        first.registration_id, store, force_validation=force_validation
    )

    assert len(validated) == int(force_validation)
    assert outcome.attempt_status == AttemptStatus.SUCCEEDED
    assert outcome.message == "No changes found."
    assert not outcome.update_applied
    assert outcome.profile_version == "v1"
    assert outcome.validation_checks[0].status == "PASSED"
    expected_status = "PASSED" if force_validation else "NOT_RUN"
    assert all(
        check.status == expected_status for check in outcome.validation_checks[1:]
    )
    assert counts(store) == (1, 1, 2)


@pytest.mark.parametrize(
    "failed_checks, is_valid, errors, reason",
    [
        (["Adapter semantics"], False, ["Broken reference"], "SEMANTICS_INVALID"),
        (["Croissant compliance"], False, ["Invalid Croissant"], "MLCROISSANT_INVALID"),
        (["Adapter schema"], False, ["Missing field"], "SCHEMA_INVALID"),
        (
            ["Adapter semantics", "Croissant compliance"],
            False,
            ["Multiple failures"],
            "SCHEMA_INVALID",
        ),
        ([], True, ["Reported error"], "SCHEMA_INVALID"),
        ([], False, [], "SCHEMA_INVALID"),
    ],
)
def test_validation_failure_preserves_reason_profile_and_details(
    repository, store, monkeypatch, failed_checks, is_valid, errors, reason
):
    from src.core.registration import service

    detail = ValidationDetail(message="Invalid metadata", json_path="$.name")
    validation = ValidationResult(
        is_valid=is_valid,
        errors=errors,
        checks=[ValidationCheck(name=name, is_valid=False) for name in failed_checks],
        profile_version="test-profile",
        validation_details=[detail],
    )
    monkeypatch.setattr(
        service,
        "validate_discovered_adapter",
        lambda candidate, **kwargs: replace(candidate, validation=validation),
    )

    outcome = register_adapter(
        str(repository), store, actor=AuthSession(github_user_id="123")
    )

    assert outcome.attempt_status == AttemptStatus.FAILED
    assert outcome.reason_code == reason
    assert outcome.validation_errors == tuple(errors or ["Metadata is invalid."])
    assert outcome.validation_details == (detail,)
    assert outcome.profile_version == "test-profile"
    assert outcome.registration is None
    assert outcome.validation_checks[0].status == "PASSED"
    assert all(check.status == "NOT_RUN" for check in outcome.validation_checks[1:])
    assert counts(store) == (0, 0, 0)


def test_stale_update_cannot_replace_a_concurrent_success(
    repository, store, monkeypatch
):
    first = register_adapter(
        str(repository), store, actor=AuthSession(github_user_id="123")
    ).registration
    document = sample_adapter_document()
    document["version"] = "1.1.0"
    (repository / "croissant.jsonld").write_text(json.dumps(document))
    from src.core.registration import service

    validate = service.validate_discovered_adapter

    def concurrent_validation(candidate, **kwargs):
        other = sample_adapter_document()
        other["version"] = "1.2.0"
        request = service.create_registration_request(
            str(repository), submitted_by_github_user_id="123"
        )
        store.accept_candidate(
            request,
            other,
            "v1",
            "example-adapter::1.2.0",
            service._metadata_checksum(other),
            first,
        )
        return validate(candidate, **kwargs)

    monkeypatch.setattr(service, "validate_discovered_adapter", concurrent_validation)
    with pytest.raises(ConcurrentRegistrationChangeError):
        update_registration(first.registration_id, store)
    assert store.get_registration(first.registration_id).metadata["version"] == "1.2.0"
    assert counts(store) == (1, 2, 2)


def test_deletion_during_processing_cannot_recreate_registration(
    repository, store, monkeypatch
):
    first = register_adapter(
        str(repository), store, actor=AuthSession(github_user_id="123")
    ).registration
    document = sample_adapter_document()
    document["version"] = "1.1.0"
    (repository / "croissant.jsonld").write_text(json.dumps(document))
    from src.core.registration import service

    validate = service.validate_discovered_adapter

    def delete_during_validation(candidate, **kwargs):
        store.remove_adapter(first.adapter_id, [first.registration_id])
        return validate(candidate, **kwargs)

    monkeypatch.setattr(
        service, "validate_discovered_adapter", delete_during_validation
    )
    with pytest.raises(ConcurrentRegistrationChangeError):
        update_registration(first.registration_id, store)
    assert counts(store) == (0, 0, 0)
