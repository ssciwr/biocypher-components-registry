"""Metadata validation routes."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from fastapi import APIRouter, HTTPException, status

from src.api.schemas.metadata import (
    AdapterEmbeddedDatasetGenerateRequest,
    AdapterMetadataGenerateRequest,
    AdapterMetadataGenerateResponse,
    DatasetMetadataGenerateRequest,
    DatasetMetadataGenerateResponse,
    MetadataValidationRequest,
    MetadataValidationResponse,
)
from src.core.adapter.request import AdapterGenerationRequest
from src.core.adapter.service import execute_request as execute_adapter_request
from src.core.dataset.request import GenerationRequest
from src.core.dataset.service import execute_request as execute_dataset_request
from src.core.validation import validate_adapter_with_embedded_datasets, validate_dataset
from src.core.validation.results import ValidationResult


router = APIRouter()


# ===========================================================
# Metadata Routes
# ===========================================================


@router.post(
    "/metadata/validate",
    response_model=MetadataValidationResponse,
    summary="Validate metadata",
    description=(
        "Validate an inline Croissant adapter or dataset document without "
        "persisting it. Adapter validation includes the adapter document and "
        "each embedded dataset fragment. Validation failures return 200 with "
        "is_valid=false; malformed requests return 422."
    ),
)
def validate_metadata(
    payload: MetadataValidationRequest,
) -> MetadataValidationResponse:
    """Validate adapter or dataset metadata without persisting it."""
    kind = _resolve_validation_kind(payload.kind, payload.metadata)
    result = _validate_by_kind(kind, payload.metadata)
    return MetadataValidationResponse.from_result(kind=kind, result=result)


@router.post(
    "/metadata/datasets/generate",
    response_model=DatasetMetadataGenerateResponse,
    summary="Generate dataset metadata",
    description=(
        "Generate dataset Croissant metadata from a server-side input path. "
        "The backend writes to a temporary file, returns the generated metadata "
        "in the response, and validates by default."
    ),
)
def generate_dataset_metadata(
    payload: DatasetMetadataGenerateRequest,
) -> DatasetMetadataGenerateResponse:
    """Generate dataset metadata from server-side files without persisting it."""
    with TemporaryDirectory() as temporary_directory:
        output_path = Path(temporary_directory) / "dataset.jsonld"
        request = _build_dataset_generation_request(
            payload=payload,
            output_path=output_path,
        )

        try:
            result = execute_dataset_request(
                request=request,
                generator=payload.generator,
            )
            metadata = _load_generated_metadata(
                document=result.document,
                output_path=output_path,
            )
        except (json.JSONDecodeError, OSError, RuntimeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        validation = _optional_validation_response(
            should_validate=payload.run_validation,
            kind="dataset",
            metadata=metadata,
        )

        return DatasetMetadataGenerateResponse(
            metadata=metadata,
            generator=payload.generator,
            stdout=result.stdout,
            stderr=result.stderr,
            warnings=result.warnings,
            validation=validation,
        )


@router.post(
    "/metadata/adapters/generate",
    response_model=AdapterMetadataGenerateResponse,
    summary="Generate adapter metadata",
    description=(
        "Generate adapter Croissant metadata from existing dataset metadata "
        "files and/or generated embedded datasets. Paths are server-side paths "
        "visible to the backend process. The endpoint returns metadata without "
        "creating a registration."
    ),
)
def generate_adapter_metadata(
    payload: AdapterMetadataGenerateRequest,
) -> AdapterMetadataGenerateResponse:
    """Generate adapter metadata from existing or generated datasets."""
    with TemporaryDirectory() as temporary_directory:
        output_path = Path(temporary_directory) / "adapter.jsonld"
        request = _build_adapter_generation_request(
            payload=payload,
            output_path=output_path,
        )

        try:
            result = execute_adapter_request(
                request=request,
                generator=payload.generator,
            )
            metadata = _load_generated_metadata(
                document=result.document,
                output_path=output_path,
            )
        except (json.JSONDecodeError, OSError, RuntimeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        validation = _optional_validation_response(
            should_validate=payload.run_validation,
            kind="adapter",
            metadata=metadata,
        )

        return AdapterMetadataGenerateResponse(
            metadata=metadata,
            generator=payload.generator,
            dataset_generator=payload.dataset_generator,
            stdout=result.stdout,
            stderr=result.stderr,
            warnings=result.warnings,
            validation=validation,
        )


# ===========================================================
# Route Helpers
# ===========================================================


def _resolve_validation_kind(
    requested_kind: Literal["auto", "adapter", "dataset"],
    metadata: dict[str, object],
) -> Literal["adapter", "dataset"]:
    """Resolve the metadata type requested by the client."""
    if requested_kind != "auto":
        return requested_kind

    root_type = metadata.get("@type")
    if root_type in {"SoftwareSourceCode", "sc:SoftwareSourceCode"}:
        return "adapter"
    if root_type in {"Dataset", "sc:Dataset"}:
        return "dataset"

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=(
            "Could not detect metadata type automatically. "
            "Use kind='adapter' or kind='dataset'."
        ),
    )


def _validate_by_kind(
    kind: Literal["adapter", "dataset"],
    metadata: dict[str, object],
) -> ValidationResult:
    """Run the core validator selected by metadata kind."""
    if kind == "adapter":
        return validate_adapter_with_embedded_datasets(metadata)
    return validate_dataset(metadata)


def _optional_validation_response(
    *,
    should_validate: bool,
    kind: Literal["adapter", "dataset"],
    metadata: dict[str, object],
) -> MetadataValidationResponse | None:
    """Build a validation response when the generation request asks for one."""
    if not should_validate:
        return None

    validation_result = _validate_by_kind(kind, metadata)
    return MetadataValidationResponse.from_result(
        kind=kind,
        result=validation_result,
    )


def _build_dataset_generation_request(
    *,
    payload: DatasetMetadataGenerateRequest,
    output_path: Path,
) -> GenerationRequest:
    """Translate the API request into the core dataset generation contract."""
    return _build_core_dataset_generation_request(
        payload=payload,
        output_path=str(output_path),
    )


def _build_adapter_generation_request(
    *,
    payload: AdapterMetadataGenerateRequest,
    output_path: Path,
) -> AdapterGenerationRequest:
    """Translate the API request into the core adapter generation contract."""
    return AdapterGenerationRequest(
        output_path=str(output_path),
        name=payload.name,
        description=payload.description,
        version=payload.version,
        license_value=payload.license_value,
        code_repository=payload.code_repository,
        dataset_paths=payload.dataset_paths,
        validate=payload.run_validation,
        creators=payload.creators,
        keywords=payload.keywords,
        adapter_id=payload.adapter_id,
        programming_language=payload.programming_language,
        target_product=payload.target_product,
        dataset_generator=payload.dataset_generator,
        generated_datasets=[
            _build_embedded_dataset_generation_request(dataset)
            for dataset in payload.generated_datasets
        ],
    )


def _build_embedded_dataset_generation_request(
    payload: AdapterEmbeddedDatasetGenerateRequest,
) -> GenerationRequest:
    """Translate one generated embedded dataset into the core dataset contract."""
    return _build_core_dataset_generation_request(
        payload=payload,
        output_path="",
    )


def _build_core_dataset_generation_request(
    *,
    payload: DatasetMetadataGenerateRequest | AdapterEmbeddedDatasetGenerateRequest,
    output_path: str,
) -> GenerationRequest:
    """Translate shared dataset generation API fields into the core contract."""
    return GenerationRequest(
        input_path=payload.input_path,
        output_path=output_path,
        validate=payload.run_validation,
        name=payload.name,
        description=payload.description,
        url=payload.url,
        license_value=payload.license_value,
        citation=payload.citation,
        dataset_version=payload.dataset_version,
        date_published=payload.date_published,
        creators=payload.creators,
        extra_args=payload.extra_args,
    )


def _load_generated_metadata(
    *,
    document: dict[str, object] | None,
    output_path: Path,
) -> dict[str, object]:
    """Return the generated document from memory or the temporary output file."""
    if document is not None:
        return document

    return json.loads(output_path.read_text(encoding="utf-8"))
