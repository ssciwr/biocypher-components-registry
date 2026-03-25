"""Config parsing helpers for dataset generation commands."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

import typer
import yaml

from src.core.dataset.request import GenerationRequest


def request_from_config(
    config_path: str,
    output_override: str | None = None,
) -> GenerationRequest:
    """Build a dataset request from YAML configuration.

    Args:
        config_path: Path to the YAML file.
        output_override: Optional output path override.

    Returns:
        A normalized dataset generation request.
    """
    raw = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise typer.BadParameter("Config file must contain a YAML mapping at the top level.")

    metadata = raw.get("metadata", {})
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        raise typer.BadParameter("'metadata' must be a mapping if provided.")

    input_path = _pick_first_value(raw, metadata, keys=("input",))
    if not input_path:
        raise typer.BadParameter("Config file must define 'input'.")

    output_path = (
        output_override
        or _pick_first_value(raw, metadata, keys=("output",))
        or "croissant.jsonld"
    )
    validate = bool(
        _pick_first_value(raw, metadata, keys=("validate",), default=True)
    )

    creators = _parse_creators(
        _pick_first_value(raw, metadata, keys=("creators",), default=[])
    )
    extra_args = _parse_extra_args(raw.get("extra_args", []))

    return GenerationRequest(
        input_path=str(input_path),
        output_path=str(output_path),
        validate=validate,
        name=_pick_first_value(raw, metadata, keys=("name",)),
        description=_pick_first_value(raw, metadata, keys=("description",)),
        url=_pick_first_value(raw, metadata, keys=("url",)),
        license_value=_pick_first_value(raw, metadata, keys=("license",)),
        citation=_pick_first_value(raw, metadata, keys=("citation",)),
        dataset_version=_pick_first_value(
            raw, metadata, keys=("dataset_version", "dataset-version")
        ),
        date_published=_pick_first_value(
            raw, metadata, keys=("date_published", "date-published")
        ),
        creators=creators,
        extra_args=extra_args,
    )


def _pick_first_value(
    *mappings: dict[str, Any], keys: tuple[str, ...], default: Any = None
) -> Any:
    """Return the first non-empty value across candidate mappings and keys."""
    for key in keys:
        for mapping in mappings:
            if key in mapping and mapping[key] not in (None, ""):
                value = mapping[key]
                if isinstance(value, (date, datetime)):
                    return value.isoformat()
                return value
    return default


def _parse_creators(raw_creators: Any) -> list[str]:
    """Normalize creator entries from YAML into compact CLI-style strings."""
    if raw_creators in (None, ""):
        return []
    if not isinstance(raw_creators, list):
        raise typer.BadParameter("'creators' must be a list.")

    creators: list[str] = []
    for entry in raw_creators:
        if isinstance(entry, str):
            creators.append(entry)
            continue
        if isinstance(entry, dict):
            name = str(entry.get("name", "")).strip()
            email = str(entry.get("email", "")).strip()
            url = str(entry.get("url", "")).strip()
            if not name:
                raise typer.BadParameter("Each creator mapping must define 'name'.")
            creators.append(_format_creator(name, email, url))
            continue
        raise typer.BadParameter("Each creator must be a string or mapping.")

    return creators


def _parse_extra_args(extra_args: Any) -> list[str]:
    """Validate optional passthrough CLI arguments from configuration."""
    if extra_args in (None, ""):
        return []
    if not isinstance(extra_args, list) or not all(isinstance(arg, str) for arg in extra_args):
        raise typer.BadParameter("'extra_args' must be a list of strings.")
    return list(extra_args)


def _format_creator(name: str, email: str, url: str) -> str:
    """Serialize creator fields into the compact dataset creator format."""
    parts = [name]
    if email or url:
        parts.append(email)
    if url:
        if not email:
            parts.append("")
        parts.append(url)
    return ",".join(parts)
