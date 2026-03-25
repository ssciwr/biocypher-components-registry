"""Native adapter backend that assembles metadata documents in-process."""

from __future__ import annotations

from dataclasses import replace
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from src.core.adapter.request import AdapterGenerationRequest
from src.core.adapter.backends.base import AdapterGenerator
from src.core.adapter.document import (
    build_adapter_creator,
    build_adapter_document,
)
from src.core.dataset.service import execute_request as execute_dataset_request
from src.core.dataset.request import GenerationResult
from src.core.shared.creators import parse_adapter_creator_string
from src.core.shared.errors import GeneratorError
from src.core.shared.ids import slugify_identifier
from src.core.shared.licenses import normalize_license_url
from src.core.validation import validate_adapter_with_embedded_datasets, validate_dataset


class NativeAdapterGenerator(AdapterGenerator):
    """Generate adapter metadata from existing or generated dataset documents."""

    name = "native"

    def generate(self, request: AdapterGenerationRequest) -> GenerationResult:
        """Build, serialize, and optionally validate adapter metadata."""
        datasets = [self._load_dataset(path) for path in request.dataset_paths]
        dataset_reports: list[str] = []
        for dataset_index, dataset_request in enumerate(request.generated_datasets, start=1):
            dataset_document, dataset_stdout, dataset_stderr = self._generate_dataset(
                request.dataset_generator,
                dataset_request,
            )
            datasets.append(dataset_document)
            report_parts: list[str] = []
            if dataset_stdout.strip():
                report_parts.append(dataset_stdout.strip())
            if dataset_stderr.strip():
                report_parts.append(dataset_stderr.strip())
            if report_parts:
                dataset_name = dataset_request.name or f"dataset-{dataset_index}"
                dataset_reports.append(
                    f"Generated dataset '{dataset_name}'\n" + "\n".join(report_parts)
                )
        datasets = [
            _namespace_embedded_dataset(dataset, index)
            for index, dataset in enumerate(datasets, start=1)
        ]
        document = build_adapter_document(
            name=request.name,
            description=request.description,
            version=request.version,
            license_value=normalize_license_url(request.license_value),
            code_repository=request.code_repository,
            creators=_build_creators(request.creators),
            keywords=request.keywords,
            datasets=datasets,
            adapter_id=request.adapter_id,
            programming_language=request.programming_language,
            target_product=request.target_product,
        )

        output_path = Path(request.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        stdout_lines = [
            "Success! Generated adapter Croissant metadata",
            f"Datasets: {len(datasets)}",
            f"Saved to: {output_path}",
        ]
        stderr_lines: list[str] = []
        if dataset_reports:
            stdout_lines.extend(["", *dataset_reports])

        if request.validate:
            validation_result = validate_adapter_with_embedded_datasets(document)
            if validation_result.is_valid:
                stdout_lines.insert(0, "Validation completed!")
            else:
                stderr_lines.append(
                    "Validation errors: " + "; ".join(validation_result.errors)
                )

        return GenerationResult(
            output_path=str(output_path),
            stdout="\n".join(stdout_lines),
            stderr="\n".join(stderr_lines),
            document=document,
        )

    def _generate_dataset(self, generator: str, request) -> tuple[dict[str, Any], str, str]:
        """Generate one nested dataset document through the dataset service."""
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "croissant_dataset.jsonld"
            dataset_request = replace(
                request,
                output_path=str(output_path),
            )
            result = execute_dataset_request(
                request=dataset_request,
                generator=generator,
            )
            document = result.document
            if document is None:
                document = json.loads(output_path.read_text(encoding="utf-8"))
            validation_result = validate_dataset(document)
            if not validation_result.is_valid:
                raise GeneratorError(
                    "Generated dataset metadata is not a valid Croissant dataset: "
                    + "; ".join(validation_result.errors)
                )
            return (
                _normalise_embedded_dataset(document),
                result.stdout,
                result.stderr,
            )

    def _load_dataset(self, path: str) -> dict[str, Any]:
        """Load and validate an existing dataset document from disk."""
        dataset_path = Path(path).expanduser()
        if not dataset_path.exists():
            raise GeneratorError(f"Dataset metadata file does not exist: {dataset_path}")

        try:
            document = json.loads(dataset_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise GeneratorError(
                f"Dataset metadata file is not valid JSON: {dataset_path}"
            ) from exc

        result = validate_dataset(document)
        if not result.is_valid:
            raise GeneratorError(
                f"Dataset metadata file is not a valid Croissant dataset: {dataset_path}. "
                + "; ".join(result.errors)
            )
        return _normalise_embedded_dataset(document)


def _build_creators(raw_creators: list[str]) -> list[dict[str, Any]]:
    """Parse serialized creator strings into adapter creator objects."""
    creators: list[dict[str, Any]] = []
    for raw in raw_creators:
        spec = parse_adapter_creator_string(raw)
        if spec and spec.name:
            creators.append(
                build_adapter_creator(
                    name=spec.name,
                    affiliation=spec.affiliation,
                    identifier=spec.identifier,
                    creator_type=spec.creator_type,
                )
            )
    return creators


def _normalise_embedded_dataset(document: dict[str, Any]) -> dict[str, Any]:
    """Remove standalone-only fields before embedding a dataset in an adapter."""
    dataset = dict(document)
    dataset.pop("@context", None)

    creators = dataset.get("creator")
    if isinstance(creators, dict):
        dataset["creator"] = [creators]

    return dataset


def _namespace_embedded_dataset(document: dict[str, Any], index: int) -> dict[str, Any]:
    """Namespace local ``@id`` values to avoid collisions across datasets."""
    dataset = deepcopy(document)
    prefix = f"{slugify_identifier(dataset.get('name') or f'dataset-{index}')}-{index}"
    id_map = _collect_internal_id_map(dataset, prefix)
    return _rewrite_dataset_ids(dataset, id_map)


def _collect_internal_id_map(document: Any, prefix: str) -> dict[str, str]:
    """Collect local identifier rewrites for one embedded dataset document."""
    id_map: dict[str, str] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            node_id = node.get("@id")
            if (
                isinstance(node_id, str)
                and node_id
                and not node_id.startswith(("#", "http://", "https://"))
            ):
                id_map.setdefault(node_id, f"{prefix}/{node_id}")
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(document)
    return id_map


def _rewrite_dataset_ids(document: Any, id_map: dict[str, str]) -> Any:
    """Rewrite local identifiers in a nested dataset document."""
    if isinstance(document, dict):
        rewritten = {}
        for key, value in document.items():
            if key == "@id" and isinstance(value, str):
                rewritten[key] = id_map.get(value, value)
            else:
                rewritten[key] = _rewrite_dataset_ids(value, id_map)
        return rewritten
    if isinstance(document, list):
        return [_rewrite_dataset_ids(item, id_map) for item in document]
    if isinstance(document, str):
        return id_map.get(document, document)
    return document
