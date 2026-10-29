"""Adapter metadata validator.

Validates a parsed ``croissant.jsonld`` dict against the active adapter
JSON Schema (Draft 7). The schema accepts JSON-LD singleton or list forms
for fields Croissant commonly serializes either way.

In addition to JSON Schema, this module also performs lightweight
Croissant-specific semantic checks such as duplicate node ``@id`` values
and broken ``fileObject`` references from fields.
"""

from __future__ import annotations

from typing import Any

import jsonschema.validators

from src.core.schema import profile
from src.core.validation.dataset import validate_embedded_dataset
from src.core.validation.mlcroissant import validate_with_mlcroissant
from src.core.validation.progress import ValidationProgress, croissant_validator_info
from src.core.validation.results import (
    ValidationCheck,
    ValidationCheckReport,
    ValidationResult,
)
from src.core.validation.schema_diagnostics import (
    format_schema_error,
    schema_validation_details,
)


def validate_adapter(
    data: dict[str, Any], *, progress: ValidationProgress | None = None
) -> ValidationResult:
    """Validate adapter metadata against the active adapter schema."""
    progress = progress or ValidationProgress()
    profile_version = profile.ACTIVE_PROFILE_VERSION
    schema = profile.load_schema(profile_version)

    validator_cls = jsonschema.validators.validator_for(schema)
    validator = validator_cls(schema)

    progress.update("croissant", status="RUNNING", **croissant_validator_info())
    mlcroissant_errors = validate_with_mlcroissant(data)
    progress.update(
        "croissant",
        status="FAILED" if mlcroissant_errors else "PASSED",
        errors=tuple(mlcroissant_errors),
    )
    progress.update(
        "schema",
        status="RUNNING",
        profile_version=profile_version,
        schema_title=schema.get("title"),
        schema_id=schema.get("$id"),
        schema_dialect=schema.get("$schema"),
        validator_name="jsonschema",
    )
    raw_schema_errors = list(validator.iter_errors(data))
    schema_errors = [format_schema_error(err) for err in raw_schema_errors]
    schema_details = schema_validation_details(
        raw_schema_errors, schema, getattr(data, "json_source", None)
    )
    progress.update(
        "schema",
        status="FAILED" if schema_errors else "PASSED",
        errors=tuple(schema_errors),
        validation_details=tuple(schema_details),
    )
    progress.update("semantics", status="RUNNING")
    semantic_errors = _semantic_errors(data)
    progress.update(
        "semantics",
        status="FAILED" if semantic_errors else "PASSED",
        errors=tuple(semantic_errors),
    )
    checks = [
        ValidationCheck(
            name="Croissant compliance",
            is_valid=len(mlcroissant_errors) == 0,
            errors=mlcroissant_errors,
        ),
        ValidationCheck(
            name="Adapter schema",
            is_valid=len(schema_errors) == 0,
            errors=schema_errors,
            validation_details=schema_details,
        ),
        ValidationCheck(
            name="Adapter semantics",
            is_valid=len(semantic_errors) == 0,
            errors=semantic_errors,
        ),
    ]

    errors: list[str] = []
    errors.extend(mlcroissant_errors)
    errors.extend(schema_errors)
    errors.extend(semantic_errors)

    return ValidationResult(
        is_valid=all(check.is_valid for check in checks),
        errors=errors,
        checks=checks,
        profile_version=profile_version,
        validation_checks=progress.reports,
        validation_details=[
            detail for check in checks for detail in check.validation_details
        ],
    )


def validate(data: dict[str, Any]) -> ValidationResult:
    """Backward-compatible alias for adapter validation."""
    return validate_adapter(data)


def validate_adapter_with_embedded_datasets(
    data: dict[str, Any], *, progress: ValidationProgress | None = None
) -> ValidationResult:
    """Validate adapter metadata and each embedded dataset fragment.

    This is the registry-level adapter validation contract used by user-facing
    interfaces. It keeps the adapter schema/compliance checks and embedded
    dataset checks together so the API, CLI, and registration workflow
    agree on what a valid adapter means.
    """
    progress = progress or ValidationProgress(include_datasets=True)
    if not any(check.id == "datasets" for check in progress.reports):
        progress.put(ValidationCheckReport("datasets", "Embedded datasets"))
    adapter_result = validate_adapter(data, progress=progress)
    embedded_checks = _embedded_dataset_checks(data, progress)
    checks = [*adapter_result.checks, *embedded_checks]
    errors = [error for check in checks for error in check.errors]

    return ValidationResult(
        is_valid=all(check.is_valid for check in checks),
        errors=errors,
        checks=checks,
        profile_version=adapter_result.profile_version,
        validation_checks=progress.reports,
        validation_details=[
            detail for check in checks for detail in check.validation_details
        ],
    )


def _embedded_dataset_checks(
    data: dict[str, Any], progress: ValidationProgress
) -> list[ValidationCheck]:
    """Validate each embedded dataset as a standalone Croissant dataset."""
    has_part = data.get("hasPart")
    if isinstance(has_part, dict):
        has_part = [has_part]
    if not isinstance(has_part, list) or not has_part:
        progress.update(
            "datasets",
            status="NOT_RUN",
            reason="No embedded dataset objects are available. See the adapter schema result.",
        )
        return []

    progress.update("datasets", status="RUNNING")
    for index, dataset in enumerate(has_part):
        label = (
            str(dataset.get("name") or f"Dataset {index + 1}")
            if isinstance(dataset, dict)
            else f"Dataset {index + 1}"
        )
        progress.put(
            ValidationCheckReport(
                id=f"dataset:{index}",
                name=label,
                parent_id="datasets",
                dataset_index=index,
                dataset_name=label,
            )
        )
    checks: list[ValidationCheck] = []
    for index, dataset in enumerate(has_part, start=1):
        check_id = f"dataset:{index - 1}"
        if not isinstance(dataset, dict):
            progress.update(
                check_id,
                status="NOT_RUN",
                reason="This hasPart item is not an object. See the adapter schema result.",
            )
            continue
        progress.update(check_id, status="RUNNING", **croissant_validator_info())
        label = str(dataset.get("name") or f"dataset[{index}]")
        result = validate_embedded_dataset(dataset)
        progress.update(
            check_id,
            status="PASSED" if result.is_valid else "FAILED",
            errors=tuple(f"[{label}] {error}" for error in result.errors),
            validation_details=tuple(result.validation_details),
        )
        checks.append(
            ValidationCheck(
                name=f"Embedded dataset: {label}",
                is_valid=result.is_valid,
                errors=[f"[{label}] {error}" for error in result.errors],
            )
        )
    _complete_dataset_group(progress)
    return checks


def _complete_dataset_group(progress: ValidationProgress) -> None:
    """Finalize the group, giving failed checks precedence over skipped checks."""
    children = [check for check in progress.reports if check.parent_id == "datasets"]
    status = "PASSED"
    if any(check.status == "FAILED" for check in children):
        status = "FAILED"
    elif any(check.status == "NOT_RUN" for check in children):
        status = "NOT_RUN"
    progress.update(
        "datasets",
        status=status,
        reason="Some dataset checks could not run. See their results below."
        if status == "NOT_RUN"
        else None,
    )


def _semantic_errors(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    errors.extend(_duplicate_id_errors(data))
    errors.extend(_file_object_reference_errors(data))
    return errors


def _duplicate_id_errors(data: dict[str, Any]) -> list[str]:
    occurrences: dict[str, list[str]] = {}
    _collect_id_occurrences(data, "", occurrences)

    errors: list[str] = []
    for node_id, paths in sorted(occurrences.items()):
        if len(paths) > 1:
            locations = ", ".join(paths)
            errors.append(
                f"Duplicate @id {node_id!r} found in multiple nodes: {locations}."
            )
    return errors


def _collect_id_occurrences(
    node: Any, path: str, occurrences: dict[str, list[str]]
) -> None:
    """Recursively record ``@id`` occurrences and the paths where they appear."""
    if isinstance(node, dict):
        _record_node_id(node, path, occurrences)
        for key, value in node.items():
            child_path = f"{path}.{key}" if path else key
            _collect_id_occurrences(value, child_path, occurrences)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            child_path = f"{path}[{index}]" if path else f"[{index}]"
            _collect_id_occurrences(value, child_path, occurrences)


def _record_node_id(
    node: dict[str, Any], path: str, occurrences: dict[str, list[str]]
) -> None:
    """Record a node's ``@id`` occurrence when it defines (not just references) one."""
    node_id = node.get("@id")
    if isinstance(node_id, str) and node_id and _is_node_definition(node):
        occurrences.setdefault(node_id, []).append(path or "$")


def _is_node_definition(node: dict[str, Any]) -> bool:
    keys = set(node)
    return keys != {"@id"}


def _file_object_reference_errors(data: dict[str, Any]) -> list[str]:
    has_part = data.get("hasPart")
    if isinstance(has_part, dict):
        has_part = [has_part]
    if not isinstance(has_part, list):
        return []

    errors: list[str] = []
    for dataset_index, dataset in enumerate(has_part):
        if not isinstance(dataset, dict):
            continue
        errors.extend(_dataset_file_object_errors(dataset_index, dataset))
    return errors


def _dataset_file_object_errors(
    dataset_index: int, dataset: dict[str, Any]
) -> list[str]:
    """Validate ``fileObject`` references for every recordSet in a dataset."""
    dataset_name = str(dataset.get("name") or f"dataset[{dataset_index}]")
    distribution_ids = _distribution_ids(dataset)
    record_sets = dataset.get("recordSet")
    if not isinstance(record_sets, list):
        return []

    errors: list[str] = []
    for record_set_index, record_set in enumerate(record_sets):
        if not isinstance(record_set, dict):
            continue
        errors.extend(
            _record_set_file_object_errors(
                dataset_index,
                dataset_name,
                record_set_index,
                record_set,
                distribution_ids,
            )
        )
    return errors


def _record_set_file_object_errors(
    dataset_index: int,
    dataset_name: str,
    record_set_index: int,
    record_set: dict[str, Any],
    distribution_ids: set[str],
) -> list[str]:
    """Validate ``fileObject`` references for every field in a recordSet."""
    record_set_name = str(
        record_set.get("name")
        or record_set.get("@id")
        or f"recordSet[{record_set_index}]"
    )
    fields = record_set.get("field")
    if not isinstance(fields, list):
        return []

    errors: list[str] = []
    for field_index, field in enumerate(fields):
        if not isinstance(field, dict):
            continue
        error = _field_file_object_error(
            dataset_index,
            dataset_name,
            record_set_index,
            record_set_name,
            field_index,
            field,
            distribution_ids,
        )
        if error is not None:
            errors.append(error)
    return errors


def _field_file_object_error(
    dataset_index: int,
    dataset_name: str,
    record_set_index: int,
    record_set_name: str,
    field_index: int,
    field: dict[str, Any],
    distribution_ids: set[str],
) -> str | None:
    """Return an error message when a field's ``fileObject`` reference is invalid."""
    field_name = str(field.get("name") or f"field[{field_index}]")
    location = (
        f"[hasPart[{dataset_index}] {dataset_name} → "
        f"recordSet[{record_set_index}] {record_set_name} → "
        f"field[{field_index}] {field_name}] "
    )
    source = field.get("source")
    if isinstance(source, list):
        return f"{location}Field 'source' must be a single object, not a list."
    if not isinstance(source, dict):
        return None
    file_object = source.get("fileObject")
    if not isinstance(file_object, dict):
        return None
    file_object_id = file_object.get("@id")
    if (
        isinstance(file_object_id, str)
        and file_object_id
        and file_object_id not in distribution_ids
    ):
        return (
            f"{location}Referenced fileObject @id {file_object_id!r} is not "
            "defined in this dataset's distribution."
        )
    return None


def _distribution_ids(dataset: dict[str, Any]) -> set[str]:
    distribution_ids: set[str] = set()
    distribution = dataset.get("distribution")
    if not isinstance(distribution, list):
        return distribution_ids
    for entry in distribution:
        if isinstance(entry, dict):
            entry_id = entry.get("@id")
            if isinstance(entry_id, str) and entry_id:
                distribution_ids.add(entry_id)
    return distribution_ids
