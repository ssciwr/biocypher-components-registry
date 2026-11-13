"""Thin wrapper around ``mlcroissant`` with normalized error reporting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import mlcroissant as mlc

from src.core.shared.constants import CROISSANT_1_0_CONTEXT

_JSONLD_CONTEXT_KEY = "@context"
_VALIDATION_REPORT_PREFIX = "Found the following "


@dataclass(frozen=True)
class MLCroissantValidationReport:
    """Exact blocking and advisory findings emitted by mlcroissant."""

    errors: list[str]
    warnings: list[str]


def validate_with_mlcroissant_report(
    document: dict[str, Any],
) -> MLCroissantValidationReport:
    """Validate a document with ``mlcroissant``.

    Args:
        document: Parsed Croissant-compatible metadata.

    Returns:
        Blocking errors and non-blocking warnings as separate lists.
    """
    shape_errors = _jsonld_shape_errors(document)
    if shape_errors:
        return MLCroissantValidationReport(shape_errors, [])
    context_warnings = _jsonld_context_warnings(document)
    try:
        dataset = mlc.Dataset(document)
    except (mlc.ValidationError, AssertionError) as exc:
        # MLCroissant's JSON-LD expander asserts when valid JSON has no graph
        # nodes (for example {}). This is invalid input, not a server failure.
        return MLCroissantValidationReport(
            _parse_validation_errors(str(exc)),
            [*context_warnings, *_parse_validation_warnings(str(exc))],
        )
    issue_warnings = sorted(dataset.metadata.ctx.issues.warnings)
    return MLCroissantValidationReport([], [*context_warnings, *issue_warnings])


def validate_with_mlcroissant(document: dict[str, Any]) -> list[str]:
    """Backward-compatible error-only validation entry point."""
    return validate_with_mlcroissant_report(document).errors


def _jsonld_context_warnings(document: dict[str, Any]) -> list[str]:
    context = document.get(_JSONLD_CONTEXT_KEY)
    if not isinstance(context, dict):
        return []
    different_keys = set(CROISSANT_1_0_CONTEXT) - set(context)
    if not different_keys:
        return []
    return [
        "WARNING: The JSON-LD `@context` is not standard. Refer to the official "
        "@context (e.g., from the example datasets in "
        "https://github.com/mlcommons/croissant/tree/main/datasets/1.0). The "
        "different keys are: {"
        + ", ".join(repr(key) for key in sorted(different_keys))
        + "}"
    ]


def _jsonld_shape_errors(value: Any, path: str = "$") -> list[str]:
    """Reject known provider argument failures without masking internal errors."""
    if isinstance(value, dict):
        return _jsonld_dict_shape_errors(value, path)
    if isinstance(value, list):
        return _jsonld_list_shape_errors(value, path)
    return []


def _jsonld_dict_shape_errors(value: dict[str, Any], path: str) -> list[str]:
    errors = _jsonld_context_errors(value, path)
    errors.extend(_jsonld_id_errors(value, path))
    for key, item in value.items():
        if key != _JSONLD_CONTEXT_KEY:
            errors.extend(_jsonld_shape_errors(item, f"{path}.{key}"))
    return errors


def _jsonld_context_errors(value: dict[str, Any], path: str) -> list[str]:
    if _JSONLD_CONTEXT_KEY not in value or isinstance(value[_JSONLD_CONTEXT_KEY], dict):
        return []
    return [
        f"{path}.{_JSONLD_CONTEXT_KEY} must be a JSON object for Croissant validation."
    ]


def _jsonld_id_errors(value: dict[str, Any], path: str) -> list[str]:
    if "@id" not in value:
        return []
    identifier = value["@id"]
    if isinstance(identifier, str) and identifier.strip():
        return []
    return [f"{path}.@id must be a non-empty string."]


def _jsonld_list_shape_errors(value: list[Any], path: str) -> list[str]:
    errors = []
    for index, item in enumerate(value):
        errors.extend(_jsonld_shape_errors(item, f"{path}[{index}]"))
    return errors


def _parse_validation_errors(message: str) -> list[str]:
    """Return only errors from an ``mlcroissant`` error/warning report."""
    lines = [line.rstrip() for line in message.splitlines() if line.strip()]
    has_sections = any(
        line.strip().startswith(_VALIDATION_REPORT_PREFIX)
        and " error(s) during the validation:" in line
        for line in lines
    )
    if not has_sections:
        bullet_errors = [
            line.strip()[3:] for line in lines if line.strip().startswith("-  ")
        ]
        return bullet_errors or [message.strip()]

    bullet_errors: list[str] = []
    reading_errors = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(_VALIDATION_REPORT_PREFIX):
            reading_errors = " error(s) during the validation:" in stripped
            continue
        if reading_errors and stripped.startswith("-  "):
            bullet_errors.append(stripped[3:])
    if bullet_errors:
        return bullet_errors
    return []


def _parse_validation_warnings(message: str) -> list[str]:
    lines = [line.rstrip() for line in message.splitlines() if line.strip()]
    warnings: list[str] = []
    reading_warnings = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(_VALIDATION_REPORT_PREFIX):
            reading_warnings = " warning(s) during the validation:" in stripped
            continue
        if reading_warnings and stripped.startswith("-  "):
            warnings.append(stripped[3:])
    return warnings
