"""Metadata validation routes."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from src.api.schemas.metadata import (
    AdapterCreatorGenerateRequest,
    AdapterEmbeddedDatasetGenerateRequest,
    AdapterMetadataGenerateRequest,
    AdapterMetadataGenerateResponse,
    DatasetMetadataGeneratePayload,
    DatasetMetadataGenerateResponse,
    MetadataValidationRequest,
    MetadataValidationResponse,
)
from src.core.adapter.request import AdapterGenerationRequest
from src.core.adapter.service import execute_request as execute_adapter_request
from src.core.dataset.request import GenerationRequest
from src.core.dataset.service import execute_request as execute_dataset_request
from src.core.validation import (
    validate_adapter_with_embedded_datasets,
    validate_dataset,
)
from src.core.validation.results import ValidationResult


router = APIRouter()


# ===========================================================
# Metadata Routes
# ===========================================================


@router.post(
    "/metadata/validate",
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
    summary="Generate dataset metadata",
    description=(
        "Generate dataset Croissant metadata from an uploaded source data file. "
        "The backend stores the upload temporarily, runs the selected generator, "
        "returns the generated metadata, and validates by default."
    ),
)
# modified lightly using AI to support data flow
def generate_dataset_metadata(
    file: Annotated[UploadFile, File(...)],
    generator: Annotated[Literal["auto", "croissant-baker", "native"], Form()] = "auto",
    run_validation: Annotated[bool, Form(alias="validate")] = True,
    name: Annotated[str | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
    url: Annotated[str | None, Form()] = None,
    license_value: Annotated[str | None, Form(alias="license")] = None,
    citation: Annotated[str | None, Form()] = None,
    content_url: Annotated[str | None, Form()] = None,
    dataset_version: Annotated[str | None, Form()] = None,
    date_published: Annotated[str | None, Form()] = None,
    encoding_format: Annotated[str | None, Form()] = None,
    filename: Annotated[str | None, Form()] = None,
    sha256: Annotated[str | None, Form()] = None,
    creators_json: Annotated[str, Form()] = "[]",
) -> DatasetMetadataGenerateResponse:
    """Generate dataset metadata from an uploaded source file."""
    with TemporaryDirectory() as temporary_directory:
        temporary_path = Path(temporary_directory)
        input_path = temporary_path / Path(file.filename or "dataset-upload").name
        with input_path.open("wb") as handle:
            shutil.copyfileobj(file.file, handle)

        payload = DatasetMetadataGeneratePayload(
            input_path=str(input_path),
            generator=generator,
            validate=run_validation,
            name=name,
            description=description,
            url=url,
            license_value=license_value,
            citation=citation,
            content_url=content_url,
            dataset_version=dataset_version,
            date_published=date_published,
            encoding_format=encoding_format,
            filename=filename,
            sha256=sha256,
            creators=_parse_creators_json(creators_json),
            extra_args=[],
        )
        return _execute_dataset_metadata_generation(
            payload=payload,
            output_path=temporary_path / "dataset.jsonld",
        )


@router.post(
    "/metadata/adapters/generate",
    summary="Generate adapter metadata",
    description=(
        "Generate adapter Croissant metadata from inline dataset documents, "
        "existing server-side dataset metadata files, and/or generated embedded "
        "datasets. The endpoint returns metadata without creating a registration."
    ),
)
def generate_adapter_metadata(
    payload: AdapterMetadataGenerateRequest,
) -> AdapterMetadataGenerateResponse:
    """Generate adapter metadata from inline, existing, or generated datasets."""
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
        except (OSError, RuntimeError, ValueError) as exc:
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

# renamed only because it was converted into a shared helper for both dataset generation routes
def _execute_dataset_metadata_generation(
    *,
    payload: DatasetMetadataGeneratePayload,
    output_path: Path,
) -> DatasetMetadataGenerateResponse:
    """Generate dataset metadata for JSON and upload request variants."""
    request = _build_core_dataset_generation_request(
        payload=payload,
        output_path=str(output_path),
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
    except (OSError, RuntimeError, ValueError) as exc:
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


# Works for Adapter or Dataset creators equally well
def _parse_creators_json(creators_json: str) -> list[AdapterCreatorGenerateRequest]:
    """Parse structured creator form data from a multipart request."""
    if not creators_json.strip():
        return []

    try:
        raw_creators = json.loads(creators_json)
        if not isinstance(raw_creators, list):
            raise ValueError("creators_json must be a JSON array.")
        return [
            AdapterCreatorGenerateRequest.model_validate(creator)
            for creator in raw_creators
        ]
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


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
        dataset_documents=payload.dataset_documents,
        validate=payload.run_validation,
        creators=[
            creator.model_dump(exclude_none=True) for creator in payload.creators
        ],
        keywords=payload.keywords,
        adapter_id=payload.adapter_id,
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
    payload: DatasetMetadataGeneratePayload | AdapterEmbeddedDatasetGenerateRequest,
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
        content_url=payload.content_url,
        dataset_version=payload.dataset_version,
        date_published=payload.date_published,
        encoding_format=payload.encoding_format,
        filename=payload.filename,
        sha256=payload.sha256,
        creators=[
            creator.model_dump(exclude_none=True) for creator in payload.creators
        ],
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
