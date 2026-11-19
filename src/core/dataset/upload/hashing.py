"""Checksum helpers for uploaded artifacts."""

from __future__ import annotations

import re

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def normalize_sha256(value: str, *, field_name: str) -> str:
    """Validate and normalize a hexadecimal SHA-256 digest."""
    normalized = value.strip().lower()
    if not _SHA256_PATTERN.fullmatch(normalized):
        raise ValueError(f"{field_name} must be a 64-character SHA-256 digest.")
    return normalized
