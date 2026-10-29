"""Structured result models returned by validation helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from src.core.schema.profile import ACTIVE_PROFILE_VERSION


@dataclass(frozen=True)
class ValidationDetail:
    """Optional structured context accompanying an unchanged validator message."""

    message: str
    json_path: str | None = None
    requirement: str | None = None
    expected_format: str | None = None
    location_description: str | None = None
    source_file: str | None = None
    source_url: str | None = None
    line: int | None = None
    column: int | None = None
    location_kind: Literal["value", "containing_object"] | None = None


@dataclass
class ValidationCheck:
    """Stores the result of one validation layer."""

    name: str
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    validation_details: list[ValidationDetail] = field(default_factory=list)


CheckStatus = Literal["PENDING", "RUNNING", "PASSED", "FAILED", "NOT_RUN"]


@dataclass(frozen=True)
class ValidationCheckReport:
    """Response-only progress and diagnostics for a single validation stage."""

    id: str
    name: str
    status: CheckStatus = "PENDING"
    description: str | None = None
    reason: str | None = None
    errors: tuple[str, ...] = ()
    validation_details: tuple[ValidationDetail, ...] = ()
    parent_id: str | None = None
    dataset_index: int | None = None
    dataset_name: str | None = None
    profile_version: str | None = None
    schema_title: str | None = None
    schema_id: str | None = None
    schema_dialect: str | None = None
    validator_name: str | None = None
    validator_version: str | None = None


@dataclass
class ValidationResult:
    """Stores the aggregated result of one validation run."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    checks: list[ValidationCheck] = field(default_factory=list)
    profile_version: str = ACTIVE_PROFILE_VERSION
    validation_details: list[ValidationDetail] = field(default_factory=list)
    validation_checks: list[ValidationCheckReport] = field(default_factory=list)
