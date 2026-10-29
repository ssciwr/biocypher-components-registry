"""Check reporting must reflect actual execution without altering acceptance."""

import json

import pytest

from src.core.schema import profile
from src.core.validation.adapter import (
    validate_adapter,
    validate_adapter_with_embedded_datasets,
)
from src.core.validation.progress import ValidationProgress
from tests.support.croissant_fixtures import sample_adapter_document


def test_reports_ordered_transitions_and_keeps_independent_checks_running():
    document = sample_adapter_document()
    document.pop("keywords")
    events = []
    progress = ValidationProgress(events.append, include_datasets=True)
    result = validate_adapter_with_embedded_datasets(document, progress=progress)
    reports = {check.id: check for check in result.validation_checks}
    assert reports["schema"].status == "FAILED"
    assert reports["schema"].validation_details[0].json_path == "$.keywords"
    assert reports["semantics"].status == "PASSED"
    assert reports["schema"].profile_version == "v1"
    assert reports["schema"].schema_dialect.endswith("draft-07/schema#")
    assert reports["croissant"].validator_name == "mlcroissant"
    assert reports["croissant"].validator_version
    assert reports["croissant"].profile_version is None
    stages = [(event.id, event.status) for event in events]
    assert stages.index(("croissant", "RUNNING")) < stages.index(("schema", "RUNNING"))
    assert stages.index(("schema", "FAILED")) < stages.index(("semantics", "RUNNING"))
    assert not any(
        check.status in {"PENDING", "RUNNING"} for check in result.validation_checks
    )


def test_actual_profile_version_is_captured_at_validation_time(monkeypatch):
    monkeypatch.setattr(profile, "ACTIVE_PROFILE_VERSION", "test-profile")
    monkeypatch.setitem(profile._SCHEMA_FILE_MAP, "test-profile", "croissant_v1.json")
    result = validate_adapter_with_embedded_datasets(sample_adapter_document())
    assert result.profile_version == "test-profile"
    schema = next(check for check in result.validation_checks if check.id == "schema")
    assert schema.profile_version == "test-profile"


def test_selected_schema_and_recorded_version_stay_consistent_during_a_run(
    monkeypatch, tmp_path
):
    schema = profile.load_schema("v1")
    schema["properties"]["name"] = {"const": "Profile-specific adapter name"}
    (tmp_path / "test-profile.json").write_text(json.dumps(schema), encoding="utf-8")
    monkeypatch.setattr(profile, "_SCHEMA_DIR", tmp_path)
    monkeypatch.setitem(profile._SCHEMA_FILE_MAP, "test-profile", "test-profile.json")
    monkeypatch.setattr(profile, "ACTIVE_PROFILE_VERSION", "test-profile")

    def change_active_profile(check):
        if check.id == "croissant" and check.status == "RUNNING":
            monkeypatch.setattr(profile, "ACTIVE_PROFILE_VERSION", "v1")

    result = validate_adapter(
        sample_adapter_document(), progress=ValidationProgress(change_active_profile)
    )

    assert profile.ACTIVE_PROFILE_VERSION == "v1"
    assert not result.is_valid
    assert result.profile_version == "test-profile"
    schema_check = next(
        check for check in result.validation_checks if check.id == "schema"
    )
    assert schema_check.status == "FAILED"
    assert schema_check.profile_version == result.profile_version
    assert len(schema_check.validation_details) == 1
    detail = schema_check.validation_details[0]
    assert detail.json_path == "$.name"
    assert detail.requirement == "Required value"
    assert "Profile-specific adapter name" in detail.message


def test_every_dataset_has_stable_index_even_with_duplicate_names():
    document = sample_adapter_document()
    dataset = document["hasPart"][0]
    document["hasPart"] = [dataset, dict(dataset), None]
    result = validate_adapter_with_embedded_datasets(document)
    datasets = [
        check for check in result.validation_checks if check.parent_id == "datasets"
    ]
    assert [check.id for check in datasets] == ["dataset:0", "dataset:1", "dataset:2"]
    assert [check.dataset_index for check in datasets] == [0, 1, 2]
    assert datasets[0].name == datasets[1].name
    assert datasets[2].status == "NOT_RUN"
    assert datasets[2].validator_version is None
    assert "not an object" in datasets[2].reason


def test_missing_datasets_are_not_reported_as_passed():
    document = sample_adapter_document()
    document.pop("hasPart")
    result = validate_adapter_with_embedded_datasets(document)
    group = next(check for check in result.validation_checks if check.id == "datasets")
    assert group.status == "NOT_RUN"
    assert group.reason


@pytest.mark.parametrize(
    "dataset_types, child_statuses, group_status",
    [
        (["sc:Dataset"], ["PASSED"], "PASSED"),
        (["Thing"], ["FAILED"], "FAILED"),
        (["sc:Dataset", None], ["PASSED", "NOT_RUN"], "NOT_RUN"),
        (["Thing", None], ["FAILED", "NOT_RUN"], "FAILED"),
        ([None], ["NOT_RUN"], "NOT_RUN"),
    ],
)
def test_dataset_group_reports_failures_before_skipped_checks(
    dataset_types, child_statuses, group_status
):
    document = sample_adapter_document()
    dataset = document["hasPart"][0]
    document["hasPart"] = [
        {**dataset, "@type": kind} if kind is not None else None
        for kind in dataset_types
    ]
    events = []
    progress = ValidationProgress(events.append, include_datasets=True)

    result = validate_adapter_with_embedded_datasets(document, progress=progress)

    children = [
        check for check in result.validation_checks if check.parent_id == "datasets"
    ]
    assert [check.status for check in children] == child_statuses
    group = next(check for check in result.validation_checks if check.id == "datasets")
    assert group.status == group_status
    assert group.reason == (
        "Some dataset checks could not run. See their results below."
        if group_status == "NOT_RUN"
        else None
    )
    assert [event.status for event in events if event.id == "datasets"] == [
        "RUNNING",
        group_status,
    ]
    assert events[-1] == group


def test_progress_observer_failure_cannot_change_validation_acceptance(caplog):
    def unavailable_observer(check):
        raise ConnectionError("Client disconnected")

    progress = ValidationProgress(unavailable_observer)
    result = validate_adapter_with_embedded_datasets(
        sample_adapter_document(), progress=progress
    )
    assert result.is_valid
    assert all(check.status == "PASSED" for check in result.validation_checks)
    assert "Could not publish validation progress" in caplog.text
