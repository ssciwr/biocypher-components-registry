"""API contracts for ephemeral browser dataset uploads."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.api.schemas.metadata import MetadataValidationResponse


class UploadInventoryEntryRequest(BaseModel):
    """One file selected by the browser and its planned artifact."""

    entry_id: str = Field(min_length=1, max_length=64)
    relative_path: str = Field(min_length=1, max_length=1024)
    original_size: int = Field(ge=0)
    logical_format: Literal["csv", "tsv"]
    compression: Literal["gzip"] | None = None
    artifact_mode: Literal["complete", "sample"]
    strategy: str
    artifact_size: int = Field(ge=0, le=1 * 1024 * 1024)
    content_url: str | None = None


class UploadGenerationRequest(BaseModel):
    """Metadata overrides used once all artifacts have arrived."""

    model_config = ConfigDict(populate_by_name=True)

    generator: Literal["auto", "croissant-baker", "native"] = "auto"
    run_validation: bool = Field(default=True, alias="validate")
    name: str | None = None
    description: str | None = None
    url: str | None = None
    license_value: str | None = Field(default=None, alias="license")
    citation: str | None = None
    dataset_version: str | None = None
    date_published: str | None = None
    creators: list[dict[str, Any]] = Field(min_length=1)

    @field_validator(
        "name",
        "description",
        "url",
        "license_value",
        "citation",
        "dataset_version",
        "date_published",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        """Trim optional metadata and collapse blank values to null."""
        normalized = value.strip() if value else ""
        return normalized or None


class UploadSessionCreateRequest(BaseModel):
    """Complete immutable source inventory sent before any artifact body."""

    source_kind: Literal["file", "folder"]
    source_name: str = Field(min_length=1, max_length=255)
    entries: list[UploadInventoryEntryRequest] = Field(min_length=1)
    generation: UploadGenerationRequest = Field(default_factory=UploadGenerationRequest)


class UploadSessionCreateResponse(BaseModel):
    """Capability and fixed limits returned for a new session."""

    session_id: str
    token: str
    max_artifact_bytes: int
    expires_in_seconds: int
    kind: Literal["session"] = "session"


class UploadArtifactResponse(BaseModel):
    """Verification result for one raw artifact upload."""

    entry_id: str
    artifact_size: int
    artifact_sha256: str
    complete_entries: int
    total_entries: int


class UploadFinalizeResponse(BaseModel):
    """Privacy-reconciled Croissant metadata returned synchronously."""

    metadata: dict[str, Any]
    generator: Literal["croissant-baker", "native"]
    validation: MetadataValidationResponse
    warnings: list[str] = Field(default_factory=list)


class UploadFinalizeAcceptedResponse(BaseModel):
    status: Literal["finalize_queued", "processing", "complete", "failed"]
    next_poll_ms: int = 1_000


class UploadSessionStatusResponse(BaseModel):
    status: str
    next_poll_ms: int = 1_000
    result: UploadFinalizeResponse | None = None
    error: str | None = None


class UploadDeleteResponse(BaseModel):
    """Idempotent deletion acknowledgement."""

    deleted: bool = True
