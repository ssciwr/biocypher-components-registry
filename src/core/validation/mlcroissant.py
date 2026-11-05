"""Thin wrapper around ``mlcroissant`` with normalized error reporting."""

from __future__ import annotations

from typing import Any

import mlcroissant as mlc

_JSONLD_CONTEXT_KEY = "@context"


def validate_with_mlcroissant(document: dict[str, Any]) -> list[str]:
    """Validate a document with ``mlcroissant``.

    Args:
        document: Parsed Croissant-compatible metadata.

    Returns:
        A list of validation error messages.
    """
    shape_errors = _jsonld_shape_errors(document)
    if shape_errors:
        return shape_errors
    try:
        mlc.Dataset(document)
    except (mlc.ValidationError, AssertionError) as exc:
        # MLCroissant's JSON-LD expander asserts when valid JSON has no graph
        # nodes (for example {}). This is invalid input, not a server failure.
        return _parse_validation_error(str(exc))
    return []


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


def _parse_validation_error(message: str) -> list[str]:
    """Split an ``mlcroissant`` error block into individual messages."""
    lines = [line.rstrip() for line in message.splitlines() if line.strip()]
    bullet_errors = [
        line.strip()[3:] for line in lines if line.strip().startswith("-  ")
    ]
    if bullet_errors:
        return bullet_errors
    return [message.strip()]
