"""Registry of available adapter generation backends."""

from __future__ import annotations

from collections.abc import Callable

from src.core.adapter.backends.base import AdapterGenerator
from src.core.adapter.backends.native import NativeAdapterGenerator
from src.core.shared.errors import UnsupportedGeneratorError


def _build_native() -> AdapterGenerator:
    """Build the default native adapter generator."""
    return NativeAdapterGenerator()


ADAPTER_GENERATOR_HANDLERS: dict[str, Callable[[], AdapterGenerator]] = {
    "native": _build_native,
}


def resolve_adapter_generator(name: str) -> AdapterGenerator:
    """Instantiate an adapter generator by registered name."""
    try:
        return ADAPTER_GENERATOR_HANDLERS[name]()
    except KeyError as exc:
        supported = ", ".join(sorted(ADAPTER_GENERATOR_HANDLERS))
        raise UnsupportedGeneratorError(
            f"Unsupported adapter generator '{name}'. Supported: {supported}."
        ) from exc


def list_adapter_generators() -> list[str]:
    """Return the registered adapter generator names."""
    return sorted(ADAPTER_GENERATOR_HANDLERS)


__all__ = [
    "AdapterGenerator",
    "NativeAdapterGenerator",
    "list_adapter_generators",
    "resolve_adapter_generator",
]
