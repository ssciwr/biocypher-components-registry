"""Validation helpers for standalone and embedded dataset metadata."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.core.dataset.document import DATASET_CONTEXT
from src.core.validation.mlcroissant import validate_with_mlcroissant
from src.core.validation.results import ValidationCheck, ValidationResult


def validate_dataset(document: dict[str, Any]) -> ValidationResult:
    """Validate a dataset document with Croissant rules.

    Args:
        document: Dataset metadata document.

    Returns:
        The validation result for the dataset.
    """
    mlcroissant_errors = validate_with_mlcroissant(document)
    checks = [
        ValidationCheck(
            name="Croissant compliance",
            is_valid=len(mlcroissant_errors) == 0,
            errors=mlcroissant_errors,
        )
    ]
    return ValidationResult(
        is_valid=all(check.is_valid for check in checks),
        errors=[error for check in checks for error in check.errors],
        checks=checks,
    )


def validate(document: dict[str, Any]) -> ValidationResult:
    """Alias for :func:`validate_dataset`."""
    return validate_dataset(document)


def validate_embedded_dataset(document: dict[str, Any]) -> ValidationResult:
    """Validate an embedded dataset after normalizing it to standalone form.

    Args:
        document: Dataset fragment embedded inside adapter metadata.

    Returns:
        The validation result for the normalized dataset document.
    """
    return validate_dataset(_as_standalone_dataset(document))


def _as_standalone_dataset(document: dict[str, Any]) -> dict[str, Any]:
    """Normalize an embedded dataset fragment into a standalone document."""
    standalone = deepcopy(document)
    standalone.setdefault("@context", deepcopy(DATASET_CONTEXT))

    if "conformsTo" not in standalone and "dct:conformsTo" in standalone:
        standalone["conformsTo"] = standalone["dct:conformsTo"]

    creators = standalone.get("creator")
    if isinstance(creators, list) and len(creators) == 1:
        standalone["creator"] = creators[0]

    return standalone
