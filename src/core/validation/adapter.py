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

import jsonschema
import jsonschema.validators

from src.core.schema.profile import load_active_schema
from src.core.validation.dataset import validate_embedded_dataset
from src.core.validation.mlcroissant import validate_with_mlcroissant
from src.core.validation.results import ValidationCheck, ValidationResult


def validate_adapter(data: dict[str, Any]) -> ValidationResult:
    """Validate adapter metadata against the active adapter schema."""
    schema = load_active_schema()

    validator_cls = jsonschema.validators.validator_for(schema)
    validator = validator_cls(schema)

    mlcroissant_errors = validate_with_mlcroissant(data)
    schema_errors = [_format_error(err) for err in validator.iter_errors(data)]
    semantic_errors = _semantic_errors(data)
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
    )


def validate(data: dict[str, Any]) -> ValidationResult:
    """Backward-compatible alias for adapter validation."""
    return validate_adapter(data)


def validate_adapter_with_embedded_datasets(data: dict[str, Any]) -> ValidationResult:
    """Validate adapter metadata and each embedded dataset fragment.

    This is the registry-level adapter validation contract used by user-facing
    interfaces. It keeps the adapter schema/compliance checks and embedded
    dataset checks together so the API, CLI, and registration workflow
    agree on what a valid adapter means.
    """
    adapter_result = validate_adapter(data)
    embedded_checks = _embedded_dataset_checks(data)
    checks = [*adapter_result.checks, *embedded_checks]
    errors = [error for check in checks for error in check.errors]

    return ValidationResult(
        is_valid=all(check.is_valid for check in checks),
        errors=errors,
        checks=checks,
        profile_version=adapter_result.profile_version,
    )


def _embedded_dataset_checks(data: dict[str, Any]) -> list[ValidationCheck]:
    """Validate each embedded dataset as a standalone Croissant dataset."""
    has_part = data.get("hasPart")
    if isinstance(has_part, dict):
        has_part = [has_part]
    if not isinstance(has_part, list):
        return []

    checks: list[ValidationCheck] = []
    for index, dataset in enumerate(has_part, start=1):
        if not isinstance(dataset, dict):
            continue
        label = str(dataset.get("name") or f"dataset[{index}]")
        result = validate_embedded_dataset(dataset)
        checks.append(
            ValidationCheck(
                name=f"Embedded dataset: {label}",
                is_valid=result.is_valid,
                errors=[f"[{label}] {error}" for error in result.errors],
            )
        )
    return checks


def _format_error(error: jsonschema.ValidationError) -> str:
    path = " → ".join(str(p) for p in error.absolute_path)
    location = f"[{path}] " if path else ""
    return f"{location}{error.message}"


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
