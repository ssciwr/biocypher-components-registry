"""Metadata validator.

Validates a parsed ``croissant.jsonld`` dict against the active JSON
Schema (Draft 7). Before validation, ``hasPart`` is normalised: if the
payload stores a single dataset as an object instead of a one-element
array, it is wrapped automatically so the schema can always expect an
array.
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
