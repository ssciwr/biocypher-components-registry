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
    try:
        mlc.Dataset(document)
    except mlc.ValidationError as exc:
        return _parse_validation_error(str(exc))
    return []


def _parse_validation_error(message: str) -> list[str]:
    """Split an ``mlcroissant`` error block into individual messages."""
    lines = [line.rstrip() for line in message.splitlines() if line.strip()]
    bullet_errors = [
        line.strip()[3:]
        for line in lines
        if line.strip().startswith("-  ")
    ]
    if bullet_errors:
        return bullet_errors
    return [message.strip()]
