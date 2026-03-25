"""Public adapter-generation and discovery API exported by the core package."""

from __future__ import annotations

from typing import Any

from src.core.adapter.request import (
    AdapterDistributionInput,
    AdapterFieldInput,
    AdapterGenerationRequest,
    AdapterRegistrationRequest,
    AdapterRecordSetInput,
)
from src.core.dataset.request import GenerationResult

__all__ = [
    "AdapterDistributionInput",
    "AdapterDiscoveryResult",
    "AdapterFieldInput",
    "AdapterGenerationRequest",
    "AdapterRegistrationRequest",
    "AdapterRecordSetInput",
    "build_adapter_request_from_mapping",
    "create_registration_request",
    "discover_local_adapter",
    "discover_remote_adapter",
    "request_from_config",
    "ensure_supported_generator",
    "execute_request",
    "validate_discovered_adapter",
]


def build_adapter_request_from_mapping(
    raw: dict[str, Any],
    output_override: str | None = None,
    dataset_generator_override: str | None = None,
) -> AdapterGenerationRequest:
    """Build an adapter generation request from a parsed mapping."""
    from src.core.adapter.config import (
        build_adapter_request_from_mapping as _build_adapter_request_from_mapping,
    )

    return _build_adapter_request_from_mapping(
        raw=raw,
        output_override=output_override,
        dataset_generator_override=dataset_generator_override,
    )


from src.core.adapter.discovery import (
    AdapterDiscoveryResult,
    discover_local_adapter,
    discover_remote_adapter,
    validate_discovered_adapter,
)


def request_from_config(
    config_path: str,
    output_override: str | None = None,
    dataset_generator_override: str | None = None,
) -> AdapterGenerationRequest:
    """Load an adapter generation request from a YAML config file."""
    from src.core.adapter.config import request_from_config as _request_from_config

    return _request_from_config(
        config_path=config_path,
        output_override=output_override,
        dataset_generator_override=dataset_generator_override,
    )


def ensure_supported_generator(generator: str) -> str:
    """Return the generator name if it is supported."""
    from src.core.adapter.service import (
        ensure_supported_generator as _ensure_supported_generator,
    )

    return _ensure_supported_generator(generator)


def create_registration_request(
    adapter_name: str,
    repository_location: str,
    contact_email: str | None = None,
) -> AdapterRegistrationRequest:
    """Create a normalized repository submission request."""
    from src.core.adapter.service import (
        create_registration_request as _create_registration_request,
    )

    return _create_registration_request(
        adapter_name=adapter_name,
        repository_location=repository_location,
        contact_email=contact_email,
    )


def execute_request(
    request: AdapterGenerationRequest,
    generator: str,
) -> GenerationResult:
    """Execute an adapter request through the configured backend."""
    from src.core.adapter.service import execute_request as _execute_request

    return _execute_request(request=request, generator=generator)
