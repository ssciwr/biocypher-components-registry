"""Service helpers for dispatching dataset generation requests."""

from __future__ import annotations

import typer

from src.core.dataset.request import GenerationRequest
from src.core.dataset.backends import list_generators, resolve_generator
from src.core.dataset.backends.croissant_baker import (
    build_croissant_baker_command as _build_croissant_baker_command,
)
from src.core.dataset.request import GenerationResult
from src.core.shared.errors import GeneratorError


def ensure_supported_generator(generator: str) -> str:
    """Validate that the requested dataset generator is registered."""
    supported_generators = list_generators()
    if generator not in supported_generators:
        supported = ", ".join(supported_generators)
        raise typer.BadParameter(
            f"Unsupported generator '{generator}'. Supported: {supported}."
        )
    return generator


def build_croissant_baker_command(
    request: GenerationRequest,
    executable: str = "croissant-baker",
) -> list[str]:
    """Build the CLI command for the ``croissant-baker`` backend."""
    return _build_croissant_baker_command(request=request, executable=executable)


def execute_request(
    request: GenerationRequest,
    generator: str,
    executable: str = "croissant-baker",
) -> GenerationResult:
    """Execute a dataset generation request with the selected backend."""
    ensure_supported_generator(generator)
    try:
        resolved = resolve_generator(generator)
        if getattr(resolved, "name", "") == "croissant-baker" and hasattr(resolved, "executable"):
            resolved.executable = executable
        return resolved.generate(request=request)
    except GeneratorError as exc:
        raise RuntimeError(str(exc)) from exc
