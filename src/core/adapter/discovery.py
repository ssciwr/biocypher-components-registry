"""Adapter discovery helpers that bridge metadata loading and validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.shared.files import fetch_local_metadata, fetch_remote_metadata
from src.core.validation import validate_adapter_with_embedded_datasets
from src.core.validation.results import ValidationResult


@dataclass(frozen=True)
class AdapterDiscoveryResult:
    """Stores the output of an adapter discovery step."""

    source: str
    metadata: dict[str, Any]
    metadata_path: Path | None = None
    validation: ValidationResult | None = None


def discover_local_adapter(repo_path: str | Path) -> AdapterDiscoveryResult:
    """Discover adapter metadata from a local repository path."""
    metadata_path, metadata = fetch_local_metadata(repo_path)
    return AdapterDiscoveryResult(
        source=str(repo_path),
        metadata_path=metadata_path,
        metadata=metadata,
    )


def discover_remote_adapter(repo_url: str) -> AdapterDiscoveryResult:
    """Discover adapter metadata from a supported remote repository URL."""
    metadata = fetch_remote_metadata(repo_url)
    return AdapterDiscoveryResult(
        source=repo_url,
        metadata=metadata,
    )


def validate_discovered_adapter(
    result: AdapterDiscoveryResult,
) -> AdapterDiscoveryResult:
    """Attach adapter validation results to a discovery result."""
    return AdapterDiscoveryResult(
        source=result.source,
        metadata=result.metadata,
        metadata_path=result.metadata_path,
        validation=validate_adapter_with_embedded_datasets(result.metadata),
    )
