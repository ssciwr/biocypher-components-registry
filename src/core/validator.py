"""Metadata validator.

Validates a parsed ``croissant.jsonld`` dict against the active JSON
Schema (Draft 7). Before validation, ``hasPart`` is normalised: if the
payload stores a single dataset as an object instead of a one-element
array, it is wrapped automatically so the schema can always expect an
array.

In addition to JSON Schema, this module also performs lightweight
Croissant-specific semantic checks such as duplicate node ``@id`` values
and broken ``fileObject`` references from fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

import jsonschema
import jsonschema.validators

from src.core.schema.profile import ACTIVE_PROFILE_VERSION, load_active_schema


@dataclass
class ValidationResult:
    """Outcome of a single validation run."""

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    profile_version: str = ACTIVE_PROFILE_VERSION


def validate(data: Dict[str, Any]) -> ValidationResult:
    """Validate a parsed metadata document against the active schema."""
    schema = load_active_schema()
    normalised = _normalise_has_part(data)

    validator_cls = jsonschema.validators.validator_for(schema)
    validator = validator_cls(schema)

    errors: List[str] = [
        _format_error(err) for err in validator.iter_errors(normalised)
    ]
    errors.extend(_semantic_errors(normalised))

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        profile_version=ACTIVE_PROFILE_VERSION,
    )


def _normalise_has_part(data: Dict[str, Any]) -> Dict[str, Any]:
    has_part = data.get("hasPart")
    if isinstance(has_part, dict):
        return {**data, "hasPart": [has_part]}
    return data


def _format_error(error: jsonschema.ValidationError) -> str:
    path = " → ".join(str(p) for p in error.absolute_path)
    location = f"[{path}] " if path else ""
    return f"{location}{error.message}"


def _semantic_errors(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    errors.extend(_duplicate_id_errors(data))
    errors.extend(_file_object_reference_errors(data))
    return errors


def _duplicate_id_errors(data: Dict[str, Any]) -> List[str]:
    occurrences: Dict[str, List[str]] = {}

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            node_id = node.get("@id")
            if (
                isinstance(node_id, str)
                and node_id
                and _is_node_definition(node)
            ):
                occurrences.setdefault(node_id, []).append(path or "$")
            for key, value in node.items():
                child_path = f"{path}.{key}" if path else key
                walk(value, child_path)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                child_path = f"{path}[{index}]" if path else f"[{index}]"
                walk(value, child_path)

    walk(data, "")
    errors: List[str] = []
    for node_id, paths in sorted(occurrences.items()):
        if len(paths) > 1:
            locations = ", ".join(paths)
            errors.append(
                f"Duplicate @id {node_id!r} found in multiple nodes: {locations}."
            )
    return errors


def _is_node_definition(node: Dict[str, Any]) -> bool:
    keys = set(node)
    if keys == {"@id"}:
        return False
    return True


def _file_object_reference_errors(data: Dict[str, Any]) -> List[str]:
    has_part = data.get("hasPart")
    if not isinstance(has_part, list):
        return []

    errors: List[str] = []
    for dataset_index, dataset in enumerate(has_part):
        if not isinstance(dataset, dict):
            continue
        dataset_name = str(dataset.get("name") or f"dataset[{dataset_index}]")
        distribution_ids = _distribution_ids(dataset)
        record_sets = dataset.get("recordSet")
        if not isinstance(record_sets, list):
            continue
        for record_set_index, record_set in enumerate(record_sets):
            if not isinstance(record_set, dict):
                continue
            record_set_name = str(
                record_set.get("name") or record_set.get("@id") or f"recordSet[{record_set_index}]"
            )
            fields = record_set.get("field")
            if not isinstance(fields, list):
                continue
            for field_index, field in enumerate(fields):
                if not isinstance(field, dict):
                    continue
                field_name = str(field.get("name") or f"field[{field_index}]")
                source = field.get("source")
                if isinstance(source, list):
                    errors.append(
                        f"[hasPart[{dataset_index}] {dataset_name} → recordSet[{record_set_index}] {record_set_name} → field[{field_index}] {field_name}] "
                        "Field 'source' must be a single object, not a list."
                    )
                    continue
                if not isinstance(source, dict):
                    continue
                file_object = source.get("fileObject")
                if not isinstance(file_object, dict):
                    continue
                file_object_id = file_object.get("@id")
                if isinstance(file_object_id, str) and file_object_id and file_object_id not in distribution_ids:
                    errors.append(
                        f"[hasPart[{dataset_index}] {dataset_name} → recordSet[{record_set_index}] {record_set_name} → field[{field_index}] {field_name}] "
                        f"Referenced fileObject @id {file_object_id!r} is not defined in this dataset's distribution."
                    )
    return errors


def _distribution_ids(dataset: Dict[str, Any]) -> set[str]:
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
