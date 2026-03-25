"""Public validation entry points for adapter and dataset metadata."""

from __future__ import annotations

from src.core.validation.adapter import (
    validate_adapter,
    validate_adapter_with_embedded_datasets,
)
from src.core.validation.dataset import validate_dataset, validate_embedded_dataset
from src.core.validation.results import ValidationResult

__all__ = [
    "ValidationResult",
    "validate_adapter",
    "validate_adapter_with_embedded_datasets",
    "validate_dataset",
    "validate_embedded_dataset",
]
