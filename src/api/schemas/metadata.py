"""Pydantic schemas for metadata validation API contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.core.validation.results import ValidationCheck, ValidationResult


# ===========================================================
# =====================  OpenAPI Examples ===================
# ===========================================================


DATASET_METADATA_GENERATE_EXAMPLE: dict[str, Any] = {
    "input_path": "/tmp/biocypher-api-dataset-demo",
    "generator": "native",
    "validate": True,
    "name": "People Demo Dataset",
    "description": "Small CSV dataset used to verify generation.",
    "url": "https://example.org/people-demo",
    "license": "https://opensource.org/licenses/MIT",
    "citation": "https://example.org/people-demo",
    "dataset_version": "1.0.0",
    "date_published": "2026-04-17",
    "creators": ["Person|Dataset Creator"],
    "extra_args": [],
}


METADATA_VALIDATE_DATASET_EXAMPLE: dict[str, Any] = {
    "kind": "dataset",
    "metadata": {
        "@context": {
            "@language": "en",
            "@vocab": "https://schema.org/",
            "cr": "http://mlcommons.org/croissant/",
            "sc": "https://schema.org/",
            "dct": "http://purl.org/dc/terms/",
            "conformsTo": "dct:conformsTo",
            "fileObject": "cr:fileObject",
            "recordSet": "cr:recordSet",
            "field": "cr:field",
            "source": "cr:source",
            "extract": "cr:extract",
            "column": "cr:column",
            "dataType": {"@id": "cr:dataType", "@type": "@vocab"},
        },
        "@type": "sc:Dataset",
        "name": "People Demo Dataset",
        "description": "Small CSV dataset used to verify validation.",
        "conformsTo": "http://mlcommons.org/croissant/1.0",
        "citeAs": "https://example.org/people-demo",
        "creator": {"@type": "sc:Person", "name": "Dataset Creator"},
        "datePublished": "2026-04-17",
        "license": "https://opensource.org/licenses/MIT",
        "url": "https://example.org/people-demo",
        "version": "1.0.0",
        "distribution": [
            {
                "@id": "people.csv",
                "@type": "cr:FileObject",
                "name": "people.csv",
                "contentUrl": "people.csv",
                "encodingFormat": "text/csv",
                "sha256": "abc123",
            }
        ],
        "recordSet": [
            {
                "@id": "people-records",
                "@type": "cr:RecordSet",
                "name": "records",
                "field": [
                    {
                        "@id": "people-records/id",
                        "@type": "cr:Field",
                        "name": "id",
                        "description": "Identifier column.",
                        "dataType": "sc:Text",
                        "source": {
                            "fileObject": {"@id": "people.csv"},
                            "extract": {"column": "id"},
                        },
                    }
                ],
            }
        ],
    },
}


ADAPTER_METADATA_GENERATE_EXAMPLE: dict[str, Any] = {
    "name": "People Adapter",
    "description": "Adapter metadata generated through the API.",
    "version": "1.0.0",
    "license": "https://opensource.org/licenses/MIT",
    "code_repository": "https://github.com/example/people-adapter",
    "dataset_paths": [],
    "generated_datasets": [
        {
            "input": "/tmp/biocypher-api-adapter-demo",
            "validate": True,
            "name": "People Dataset",
            "description": "Small people dataset.",
            "url": "https://example.org/people",
            "license": "https://opensource.org/licenses/MIT",
            "citation": "https://example.org/people",
            "dataset_version": "1.0.0",
            "date_published": "2026-04-17",
            "creators": ["Person|Dataset Creator"],
            "extra_args": [],
        }
    ],
    "validate": True,
    "creators": [
        "Person|Example Creator|Example Lab|||https://orcid.org/0000-0000-0000-0000"
    ],
    "keywords": ["adapter", "biocypher"],
    "adapter_id": "people-adapter",
    "programming_language": "Python",
    "target_product": "BioCypher",
    "generator": "native",
    "dataset_generator": "native",
}


# ===========================================================
# =====================  Input Models =======================
# ===========================================================


class _GeneratedDatasetFields(BaseModel):
    """Shared API fields for standalone and embedded dataset generation."""

    model_config = ConfigDict(populate_by_name=True)

    run_validation: bool = Field(default=True, alias="validate")
    name: str | None = None
    description: str | None = None
    url: str | None = None
    license_value: str | None = Field(default=None, alias="license")
    citation: str | None = None
    dataset_version: str | None = None
    date_published: str | None = None
    creators: list[str] = Field(default_factory=list)
    extra_args: list[str] = Field(default_factory=list)

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
    def _normalize_optional_text(cls, value: str | None) -> str | None:
        """Trim optional text fields and collapse blanks to null."""
        return _optional_text(value)

    @field_validator("creators", "extra_args")
    @classmethod
    def _normalize_text_list(cls, value: list[str]) -> list[str]:
        """Trim list items and remove blank values."""
        return _text_list(value)


class MetadataValidationRequest(BaseModel):
    """Request body for validating metadata without persisting it."""

    model_config = ConfigDict(
        json_schema_extra={"example": METADATA_VALIDATE_DATASET_EXAMPLE},
    )

    metadata: dict[str, Any] = Field(
        ...,
        min_length=1,
        description="Inline Croissant adapter or dataset metadata document.",
    )
    kind: Literal["auto", "adapter", "dataset"] = Field(
        default="auto",
        description=(
            "Metadata type to validate. Use auto to infer from the root @type."
        ),
    )


class DatasetMetadataGenerateRequest(_GeneratedDatasetFields):
    """Request body for generating dataset metadata from server-side files."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={"example": DATASET_METADATA_GENERATE_EXAMPLE},
    )

    input_path: str = Field(
        ...,
        min_length=1,
        description=(
            "Server-side file or directory path visible to the backend process."
        ),
    )
    generator: Literal["auto", "croissant-baker", "native"] = Field(
        default="auto",
        description="Dataset metadata generator backend.",
    )

    @field_validator("input_path")
    @classmethod
    def _require_input_path(cls, value: str | None) -> str:
        """Keep the server-side input path explicit."""
        return _required_text(value, field_name="Input path")


class AdapterEmbeddedDatasetGenerateRequest(_GeneratedDatasetFields):
    """Generated dataset input embedded in an adapter metadata request."""

    model_config = ConfigDict(populate_by_name=True)

    input_path: str = Field(
        ...,
        alias="input",
        min_length=1,
        description=(
            "Server-side file or directory path used to generate this embedded dataset."
        ),
    )

    @field_validator("input_path")
    @classmethod
    def _require_input_path(cls, value: str | None) -> str:
        """Keep the server-side input path explicit."""
        return _required_text(value, field_name="Input path")


class AdapterMetadataGenerateRequest(BaseModel):
    """Request body for generating adapter metadata without persisting it."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={"example": ADAPTER_METADATA_GENERATE_EXAMPLE},
    )

    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    version: str = Field(..., min_length=1)
    license_value: str = Field(..., alias="license", min_length=1)
    code_repository: str = Field(..., min_length=1)
    dataset_paths: list[str] = Field(default_factory=list)
    generated_datasets: list[AdapterEmbeddedDatasetGenerateRequest] = Field(
        default_factory=list
    )
    run_validation: bool = Field(default=True, alias="validate")
    creators: list[str] = Field(..., min_length=1)
    keywords: list[str] = Field(..., min_length=1)
    adapter_id: str | None = None
    programming_language: str = "Python"
    target_product: str = "BioCypher"
    generator: Literal["native"] = "native"
    dataset_generator: Literal["auto", "croissant-baker", "native"] = "croissant-baker"

    @field_validator(
        "name",
        "description",
        "version",
        "license_value",
        "code_repository",
        "adapter_id",
        "programming_language",
        "target_product",
    )
    @classmethod
    def _normalize_text(cls, value: str | None) -> str | None:
        """Trim text fields and reject blank required values."""
        return _optional_text(value)

    @field_validator(
        "name",
        "description",
        "version",
        "license_value",
        "code_repository",
        "programming_language",
        "target_product",
    )
    @classmethod
    def _require_text(cls, value: str | None) -> str:
        """Keep required adapter metadata fields explicit."""
        return _required_text(value)

    @field_validator("dataset_paths")
    @classmethod
    def _normalize_text_list(cls, value: list[str]) -> list[str]:
        """Trim list items and remove blank values."""
        return _text_list(value)

    @field_validator("creators", "keywords")
    @classmethod
    def _normalize_required_text_list(cls, value: list[str]) -> list[str]:
        """Trim required list items and reject blank-only lists."""
        return _required_text_list(value)


# ===========================================================
# =====================  Output Models ======================
# ===========================================================


class MetadataValidationCheckResponse(BaseModel):
    """Response model for one validation layer result."""

    name: str
    is_valid: bool
    errors: list[str]

    @classmethod
    def from_check(
        cls,
        check: ValidationCheck,
    ) -> "MetadataValidationCheckResponse":
        """Build an API response from a core validation check."""
        return cls(
            name=check.name,
            is_valid=check.is_valid,
            errors=check.errors,
        )


class MetadataValidationResponse(BaseModel):
    """Response model for one metadata validation run."""

    kind: Literal["adapter", "dataset"]
    is_valid: bool
    profile_version: str
    errors: list[str]
    checks: list[MetadataValidationCheckResponse]

    @classmethod
    def from_result(
        cls,
        *,
        kind: Literal["adapter", "dataset"],
        result: ValidationResult,
    ) -> "MetadataValidationResponse":
        """Build an API response from a core validation result."""
        return cls(
            kind=kind,
            is_valid=result.is_valid,
            profile_version=result.profile_version,
            errors=result.errors,
            checks=[
                MetadataValidationCheckResponse.from_check(check)
                for check in result.checks
            ],
        )


class DatasetMetadataGenerateResponse(BaseModel):
    """Response returned after generating dataset metadata."""

    metadata: dict[str, Any]
    generator: Literal["auto", "croissant-baker", "native"]
    stdout: str = ""
    stderr: str = ""
    warnings: list[str] = Field(default_factory=list)
    validation: MetadataValidationResponse | None = None


class AdapterMetadataGenerateResponse(BaseModel):
    """Response returned after generating adapter metadata."""

    metadata: dict[str, Any]
    generator: Literal["native"]
    dataset_generator: Literal["auto", "croissant-baker", "native"]
    stdout: str = ""
    stderr: str = ""
    warnings: list[str] = Field(default_factory=list)
    validation: MetadataValidationResponse | None = None


# ===========================================================
# =====================  Schema Helpers =====================
# ===========================================================


def _optional_text(value: str | None) -> str | None:
    """Trim optional text and represent blank values as null."""
    if value is None:
        return None

    normalized_value = value.strip()
    if not normalized_value:
        return None
    return normalized_value


def _required_text(value: str | None, field_name: str = "Field") -> str:
    """Trim required text and reject blank values."""
    normalized_value = _optional_text(value)
    if normalized_value is None:
        raise ValueError(f"{field_name} must not be blank.")
    return normalized_value


def _text_list(value: list[str]) -> list[str]:
    """Trim a list of strings and remove blank values."""
    return [item.strip() for item in value if item.strip()]


def _required_text_list(value: list[str]) -> list[str]:
    """Trim a required list of strings and reject blank-only values."""
    normalized_value = _text_list(value)
    if not normalized_value:
        raise ValueError("List must include at least one non-blank value.")
    return normalized_value
