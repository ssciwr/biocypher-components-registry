"""Config parsing helpers for adapter generation commands."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
import yaml

from src.core.adapter.request import AdapterGenerationRequest
from src.core.dataset.request import GenerationRequest
from src.core.dataset.service import (
    ensure_supported_generator as ensure_supported_dataset_backend,
)


def request_from_config(
    config_path: str,
    output_override: str | None = None,
    dataset_generator_override: str | None = None,
) -> AdapterGenerationRequest:
    """Build an adapter request from YAML configuration."""
    raw = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
    return build_adapter_request_from_mapping(
        raw=raw,
        output_override=output_override,
        dataset_generator_override=dataset_generator_override,
    )


def build_adapter_request_from_mapping(
    raw: dict[str, Any],
    output_override: str | None = None,
    dataset_generator_override: str | None = None,
) -> AdapterGenerationRequest:
    """Normalize adapter configuration data into a typed request object."""
    if not isinstance(raw, dict):
        raise typer.BadParameter("Adapter input must be a mapping.")

    adapter = raw.get("adapter", raw)
    if not isinstance(adapter, dict):
        raise typer.BadParameter("'adapter' must be a mapping if provided.")

    dataset_generator = dataset_generator_override or raw.get(
        "dataset_generator",
        raw.get("dataset-generator", "croissant-baker"),
    )
    if not isinstance(dataset_generator, str) or not dataset_generator:
        raise typer.BadParameter("'dataset_generator' must be a non-empty string.")
    ensure_supported_dataset_backend(dataset_generator)

    datasets_raw = raw.get("datasets", [])
    if datasets_raw in (None, ""):
        datasets_raw = []
    if not isinstance(datasets_raw, list):
        raise typer.BadParameter("'datasets' must be a list.")

    dataset_paths: list[str] = []
    generated_datasets: list[GenerationRequest] = []
    for entry in datasets_raw:
        if not isinstance(entry, dict):
            raise typer.BadParameter("Each dataset entry must be a mapping.")
        mode = str(entry.get("mode", "existing")).strip().lower()
        if mode == "existing":
            dataset_paths.append(required_string(entry, "path"))
        elif mode == "generate":
            generated_datasets.append(build_generated_dataset_request(entry))
        else:
            raise typer.BadParameter("Dataset mode must be one of: existing, generate.")

    creators = parse_creator_strings(adapter.get("creators", []))
    keywords = parse_keyword_list(adapter.get("keywords", []))
    if not keywords:
        raise typer.BadParameter("Adapter config must define at least one keyword.")
    if not creators:
        raise typer.BadParameter("Adapter config must define at least one creator.")
    for dataset in generated_datasets:
        if not dataset.creators:
            dataset.creators = list(creators)

    return AdapterGenerationRequest(
        output_path=output_override or str(adapter.get("output", "croissant_adapter.jsonld")),
        name=required_string(adapter, "name"),
        description=required_string(adapter, "description"),
        version=required_string(adapter, "version"),
        license_value=required_string(adapter, "license"),
        code_repository=required_string(
            adapter,
            "code_repository",
            fallback_keys=("code-repository",),
        ),
        dataset_paths=dataset_paths,
        validate=bool(raw.get("validate", adapter.get("validate", True))),
        creators=creators,
        keywords=keywords,
        adapter_id=optional_string(adapter, "adapter_id", fallback_keys=("adapter-id",)),
        dataset_generator=dataset_generator,
        generated_datasets=generated_datasets,
    )


def build_generated_dataset_request(entry: dict[str, Any]) -> GenerationRequest:
    """Build a generated dataset request nested inside an adapter config."""
    return GenerationRequest(
        input_path=required_string(entry, "input"),
        output_path="",
        validate=bool(entry.get("validate", True)),
        name=optional_string(entry, "name"),
        description=optional_string(entry, "description"),
        url=optional_string(entry, "url"),
        license_value=optional_string(entry, "license"),
        citation=optional_string(entry, "citation"),
        dataset_version=optional_string(
            entry,
            "dataset_version",
            fallback_keys=("dataset-version",),
        ),
        date_published=optional_string(
            entry,
            "date_published",
            fallback_keys=("date-published",),
        ),
        creators=parse_creator_strings(entry.get("creators", [])),
    )


def required_string(
    mapping: dict[str, Any],
    key: str,
    fallback_keys: tuple[str, ...] = (),
) -> str:
    """Read a required string value from a mapping."""
    value = optional_string(mapping, key, fallback_keys)
    if value:
        return value
    raise typer.BadParameter(f"Missing required field '{key}'.")


def optional_string(
    mapping: dict[str, Any],
    key: str,
    fallback_keys: tuple[str, ...] = (),
) -> str | None:
    """Read an optional non-empty string value from a mapping."""
    value = mapping.get(key)
    if isinstance(value, str) and value:
        return value
    for fallback_key in fallback_keys:
        alt = mapping.get(fallback_key)
        if isinstance(alt, str) and alt:
            return alt
    return None


def parse_creator_strings(value: object) -> list[str]:
    """Normalize adapter creator values into compact serialized strings."""
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise typer.BadParameter("'creators' must be a list.")
    creators: list[str] = []
    for entry in value:
        if isinstance(entry, str):
            creators.append(entry)
        elif isinstance(entry, dict):
            name = required_string(entry, "name")
            creator_type = (
                optional_string(entry, "creator_type")
                or optional_string(entry, "type")
                or "Person"
            )
            affiliation = optional_string(entry, "affiliation") or optional_string(entry, "affiliations") or ""
            email = optional_string(entry, "email") or ""
            url = optional_string(entry, "url") or ""
            identifier = optional_string(entry, "identifier") or ""
            creators.append(
                "|".join(
                    [
                        creator_type,
                        name,
                        affiliation,
                        email,
                        url,
                        identifier,
                    ]
                )
            )
        else:
            raise typer.BadParameter("Each creator must be a string or mapping.")
    return creators


def parse_keyword_list(value: object) -> list[str]:
    """Normalize keywords from a list or comma-separated string."""
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if not isinstance(value, list):
        raise typer.BadParameter("'keywords' must be a list or comma-separated string.")
    return [str(item).strip() for item in value if str(item).strip()]
