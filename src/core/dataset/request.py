"""Typed request and result models for dataset generation workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class GenerationRequest:
    """Captures user input for a dataset metadata generation run."""

    input_path: str
    output_path: str
    validate: bool = True
    name: str | None = None
    description: str | None = None
    url: str | None = None
    license_value: str | None = None
    citation: str | None = None
    dataset_version: str | None = None
    date_published: str | None = None
    creators: list[str] = field(default_factory=list)
    extra_args: list[str] = field(default_factory=list)


@dataclass(slots=True)
class InferredField:
    """Describes one inferred field from an inspected dataset file."""

    name: str
    data_type: str
    examples: list[Any] = field(default_factory=list)
    description: str = ""


@dataclass(slots=True)
class FileInspection:
    """Stores normalized schema details extracted from one source file."""

    path: Path
    encoding_format: str
    fields: list[InferredField]
    examples_count: int = 0


@dataclass(slots=True)
class GenerationResult:
    """Carries the output and logs of a generation backend invocation."""

    output_path: str
    stdout: str = ""
    stderr: str = ""
    document: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
