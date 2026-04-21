"""Structured result models returned by validation helpers."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.core.schema.profile import ACTIVE_PROFILE_VERSION


@dataclass
class ValidationCheck:
    """Stores the result of one validation layer."""

    name: str
    is_valid: bool
    errors: list[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Stores the aggregated result of one validation run."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    checks: list[ValidationCheck] = field(default_factory=list)
    profile_version: str = ACTIVE_PROFILE_VERSION
