"""Versioned web-sampling capability contract."""

from __future__ import annotations

from src.core.dataset.upload.limits import (
    MAX_ARTIFACT_BYTES,
    SUPPORTED_FORMATS,
    SUPPORTED_STRATEGIES,
)
from src.core.dataset.upload.models import UploadInventoryEntry


def validate_capability(
    *,
    logical_format: str,
    artifact_mode: str,
    strategy: str,
    original_size: int,
    compression: str | None = None,
) -> None:
    """Reject unsupported format, mode, and strategy combinations."""
    if logical_format not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported web-upload format: {logical_format}")
    if strategy not in SUPPORTED_STRATEGIES:
        raise ValueError(f"Unsupported sampling strategy: {strategy}")
    if compression not in {None, "gzip"}:
        raise ValueError(f"Unsupported web-upload compression: {compression}")
    if compression == "gzip":
        if artifact_mode != "sample":
            raise ValueError("Gzip sources must use bounded complete-row sampling.")
        expected_strategy = f"{logical_format}-gzip-complete-rows-v1"
    else:
        expected_strategy = (
            "complete-file-v1"
            if artifact_mode == "complete"
            else f"{logical_format}-complete-rows-v1"
        )
    if strategy != expected_strategy:
        raise ValueError(
            "Sampling strategy does not match the artifact mode and format."
        )
    if (
        compression is None
        and artifact_mode == "complete"
        and original_size > MAX_ARTIFACT_BYTES
    ):
        raise ValueError("Files larger than 1 MiB must use a sampling strategy.")
    if (
        compression is None
        and artifact_mode == "sample"
        and original_size <= MAX_ARTIFACT_BYTES
    ):
        raise ValueError("Files no larger than 1 MiB must use complete-file-v1.")


def validate_entry_capability(entry: UploadInventoryEntry) -> None:
    """Validate the capability tuple declared for one inventory entry."""
    validate_capability(
        logical_format=entry.logical_format,
        artifact_mode=entry.artifact_mode,
        strategy=entry.strategy,
        original_size=entry.original_size,
        compression=entry.compression,
    )
