"""Thin wrapper around ``mlcroissant`` with normalized error reporting."""

from __future__ import annotations

from typing import Any

import mlcroissant as mlc


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
    errors = []
    if isinstance(value, dict):
        if "@context" in value and not isinstance(value["@context"], dict):
            errors.append(
                f"{path}.@context must be a JSON object for Croissant validation."
            )
        if "@id" in value and (
            not isinstance(value["@id"], str) or not value["@id"].strip()
        ):
            errors.append(f"{path}.@id must be a non-empty string.")
        for key, item in value.items():
            if key != "@context":
                errors.extend(_jsonld_shape_errors(item, f"{path}.{key}"))
    elif isinstance(value, list):
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
