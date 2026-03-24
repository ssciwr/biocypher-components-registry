"""Typed request models for adapter generation and repository submission."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from src.core.dataset.request import GenerationRequest


@dataclass(slots=True)
class AdapterFieldInput:
    """Represents one field entry in an embedded dataset record set."""

    name: str
    data_type: str
    description: str = ""
    examples: list[object] = field(default_factory=list)


@dataclass(slots=True)
class AdapterRecordSetInput:
    """Represents one record set to embed inside adapter metadata."""

    name: str
    record_set_id: str
    fields: list[AdapterFieldInput] = field(default_factory=list)
    description: str = ""


@dataclass(slots=True)
class AdapterDistributionInput:
    """Represents one dataset distribution file embedded in an adapter."""

    content_url: str
    encoding_format: str
    name: str = ""
    file_id: str | None = None
    md5: str = ""
    sha256: str = ""


@dataclass(slots=True)
class AdapterGenerationRequest:
    """Captures the full input required to generate adapter metadata."""

    output_path: str
    name: str
    description: str
    version: str
    license_value: str
    code_repository: str
    dataset_paths: list[str]
    validate: bool = True
    creators: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    adapter_id: str | None = None
    programming_language: str = "Python"
    target_product: str = "BioCypher"
    dataset_generator: str = "croissant-baker"
    generated_datasets: list[GenerationRequest] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class AdapterRegistrationRequest:
    """Captures one submitted adapter registration request.

    Args:
        adapter_name: Human-readable adapter name supplied by the maintainer.
        adapter_id: Stable slug identifier derived from the adapter name.
        repository_location: Submitted local path or repository URL.
        repository_kind: Normalized repository location type.
        source: Original user-provided repository input.
        contact_email: Optional maintainer contact email for status follow-up.
    """

    adapter_name: str
    adapter_id: str
    repository_location: str
    repository_kind: Literal["local", "remote"]
    source: str
    contact_email: str | None = None

    @property
    def repository_path(self) -> Path | None:
        """Return the local repository path when the submission is local."""
        if self.repository_kind != "local":
            return None
        return Path(self.repository_location)
