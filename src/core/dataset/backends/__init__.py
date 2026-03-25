"""Registry of available dataset generation backends."""

from __future__ import annotations

from collections.abc import Callable

from src.core.dataset.backends.auto_select import (
    AutoDatasetGenerator,
    select_generator_for_request,
)
from src.core.dataset.backends.base import DatasetGenerator
from src.core.dataset.backends.croissant_baker import (
    CroissantBakerGenerator,
    build_croissant_baker_command,
)
from src.core.dataset.backends.native import NativeDatasetGenerator
from src.core.shared.errors import UnsupportedGeneratorError


GENERATOR_HANDLERS: dict[str, Callable[[], DatasetGenerator]] = {
    "auto": AutoDatasetGenerator,
    "croissant-baker": CroissantBakerGenerator,
    "native": NativeDatasetGenerator,
}


def resolve_generator(name: str) -> DatasetGenerator:
    """Instantiate a dataset generator by registered name."""
    try:
        return GENERATOR_HANDLERS[name]()
    except KeyError as exc:
        supported = ", ".join(sorted(GENERATOR_HANDLERS))
        raise UnsupportedGeneratorError(
            f"Unsupported generator '{name}'. Supported: {supported}."
        ) from exc


def list_generators() -> list[str]:
    """Return the registered dataset generator names."""
    return sorted(GENERATOR_HANDLERS)

__all__ = [
    "AutoDatasetGenerator",
    "CroissantBakerGenerator",
    "DatasetGenerator",
    "NativeDatasetGenerator",
    "build_croissant_baker_command",
    "list_generators",
    "resolve_generator",
    "select_generator_for_request",
]
