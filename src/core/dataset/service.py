"""Service helpers for dispatching dataset generation requests."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import typer

from src.core.dataset.request import GenerationRequest
from src.core.dataset.backends import list_generators, resolve_generator
from src.core.dataset.backends.croissant_baker import (
    build_croissant_baker_command as _build_croissant_baker_command,
)
from src.core.dataset.request import GenerationResult
from src.core.shared.errors import GeneratorError


def ensure_supported_generator(generator: str) -> str:
    """Validate that the requested dataset generator is registered."""
    supported_generators = list_generators()
    if generator not in supported_generators:
        supported = ", ".join(supported_generators)
        raise typer.BadParameter(
            f"Unsupported generator '{generator}'. Supported: {supported}."
        )
    return generator


def build_croissant_baker_command(
    request: GenerationRequest,
    executable: str = "croissant-baker",
) -> list[str]:
    """Build the CLI command for the ``croissant-baker`` backend."""
    return _build_croissant_baker_command(request=request, executable=executable)


def execute_request(
    request: GenerationRequest,
    generator: str,
    executable: str = "croissant-baker",
) -> GenerationResult:
    """Execute a dataset generation request with the selected backend."""
    ensure_supported_generator(generator)
    try:
        resolved = resolve_generator(generator)
        if getattr(resolved, "name", "") == "croissant-baker" and hasattr(resolved, "executable"):
            resolved.executable = executable
        return _with_distribution_metadata(
            result=resolved.generate(request=request),
            request=request,
        )
    except GeneratorError as exc:
        raise RuntimeError(str(exc)) from exc


# AI-Generated.
# Applies explicit user-edited distribution fields after any dataset backend runs.
def _with_distribution_metadata(
    *,
    result: GenerationResult,
    request: GenerationRequest,
) -> GenerationResult:
    if not _has_distribution_metadata(request):
        return result

    document = _result_document(result)
    if document is None:
        return result

    updated_document = deepcopy(document)
    distribution = _first_distribution(updated_document, request.input_path)
    _set_optional(distribution, "contentUrl", request.content_url)
    _set_optional(distribution, "encodingFormat", request.encoding_format)
    _set_optional(distribution, "name", request.filename)
    _set_optional(distribution, "sha256", request.sha256)
    _write_result_document(result.output_path, updated_document)
    return replace(result, document=updated_document)


# AI-Generated.
# Keeps the post-generation override path inactive for untouched requests.
def _has_distribution_metadata(request: GenerationRequest) -> bool:
    for value in (
        request.content_url,
        request.encoding_format,
        request.filename,
        request.sha256,
    ):
        if value is not None and value.strip():
            return True
    return False


# AI-Generated.
# Loads a generated document from memory first, then from the backend output file.
def _result_document(result: GenerationResult) -> dict[str, Any] | None:
    if result.document is not None:
        return result.document

    output_path = Path(result.output_path) if result.output_path else None
    if output_path is None or not output_path.exists():
        return None
    return json.loads(output_path.read_text(encoding="utf-8"))


# AI-Generated.
# Returns the editable FileObject, creating one only if the generator omitted it.
def _first_distribution(document: dict[str, Any], input_path: str) -> dict[str, Any]:
    distribution = document.get("distribution")
    if isinstance(distribution, list):
        fallback: dict[str, Any] | None = None
        file_object: dict[str, Any] | None = None
        input_name = Path(input_path).expanduser().name
        for item in distribution:
            if not isinstance(item, dict):
                continue
            if fallback is None:
                fallback = item
            item_type = item.get("@type")
            is_file_object = item_type in ("cr:FileObject", "FileObject")
            if isinstance(item_type, list):
                is_file_object = any(
                    value in ("cr:FileObject", "FileObject") for value in item_type
                )
            if not is_file_object:
                continue
            if item.get("name") == input_name:
                return item
            content_url = str(item.get("contentUrl") or "")
            if Path(urlparse(content_url).path).name == input_name:
                return item
            if file_object is None:
                file_object = item
        if file_object is not None:
            return file_object
        if fallback is not None:
            return fallback
        file_object: dict[str, Any] = {"@type": "cr:FileObject"}
        distribution.insert(0, file_object)
        return file_object

    if isinstance(distribution, dict):
        return distribution

    file_object = {"@type": "cr:FileObject"}
    document["distribution"] = [file_object]
    return file_object


# AI-Generated.
# Stores non-blank form overrides using Croissant's JSON-LD property names.
def _set_optional(
    document: dict[str, Any],
    key: str,
    value: str | None,
) -> None:
    normalized_value = value.strip() if value else ""
    if normalized_value:
        document[key] = normalized_value


# AI-Generated.
# Keeps file-backed generators and in-memory generators returning the same document.
def _write_result_document(
    output_path: str,
    document: dict[str, Any],
) -> None:
    if not output_path:
        return

    Path(output_path).write_text(
        json.dumps(document, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
