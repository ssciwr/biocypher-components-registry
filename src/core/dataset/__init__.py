"""Public dataset-generation API exported by the core package."""

from __future__ import annotations

from src.core.dataset.request import (
    FileInspection,
    GenerationRequest,
    GenerationResult,
    InferredField,
)

__all__ = [
    "FileInspection",
    "GenerationRequest",
    "GenerationResult",
    "InferredField",
    "build_croissant_baker_command",
    "ensure_supported_generator",
    "execute_request",
    "request_from_config",
]
def request_from_config(
    config_path: str,
    output_override: str | None = None,
) -> GenerationRequest:
    """Load a dataset generation request from a YAML config file."""
    from src.core.dataset.config import request_from_config as _request_from_config

    return _request_from_config(config_path=config_path, output_override=output_override)


def ensure_supported_generator(generator: str) -> str:
    """Return the generator name if it is supported."""
    from src.core.dataset.service import (
        ensure_supported_generator as _ensure_supported_generator,
    )

    return _ensure_supported_generator(generator)


def build_croissant_baker_command(
    request: GenerationRequest,
    executable: str = "croissant-baker",
) -> list[str]:
    """Build the backend command for a Croissant Baker dataset request."""
    from src.core.dataset.service import (
        build_croissant_baker_command as _build_croissant_baker_command,
    )

    return _build_croissant_baker_command(request=request, executable=executable)


def execute_request(
    request: GenerationRequest,
    generator: str,
    executable: str = "croissant-baker",
) -> GenerationResult:
    """Execute a dataset request through the configured backend."""
    from src.core.dataset.service import execute_request as _execute_request

    return _execute_request(
        request=request,
        generator=generator,
        executable=executable,
    )
