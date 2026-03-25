"""Parser utilities for compact creator strings used by CLI and config flows."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CreatorSpec:
    """Normalized creator fields parsed from a compact input string."""

    creator_type: str = "Person"
    name: str = ""
    affiliation: str = ""
    email: str = ""
    url: str = ""
    identifier: str = ""


def parse_dataset_creator_string(raw: str) -> CreatorSpec | None:
    """Parse a dataset creator string into structured fields.

    Args:
        raw: Creator text from CLI or configuration input.

    Returns:
        A parsed creator spec, or ``None`` when no usable name is present.
    """
    typed = _typed_creator_parts(raw)
    if typed is not None:
        return CreatorSpec(
            creator_type=typed[0],
            name=typed[1] if len(typed) > 1 else "",
            affiliation=typed[2] if len(typed) > 2 else "",
            email=typed[3] if len(typed) > 3 else "",
            url=typed[4] if len(typed) > 4 else "",
            identifier=typed[5] if len(typed) > 5 else "",
        )

    parts = _split_untyped(raw, "|" if "|" in raw else ",")
    name = parts[0] if parts else ""
    if not name:
        return None
    return CreatorSpec(
        name=name,
        email=parts[1] if len(parts) > 1 else "",
        url=parts[2] if len(parts) > 2 else "",
    )


def parse_adapter_creator_string(raw: str) -> CreatorSpec | None:
    """Parse an adapter creator string into structured fields.

    Args:
        raw: Creator text from CLI or configuration input.

    Returns:
        A parsed creator spec, or ``None`` when no usable name is present.
    """
    typed = _typed_creator_parts(raw)
    if typed is not None:
        identifier = typed[5] if len(typed) > 5 else (typed[4] if len(typed) > 4 else "")
        return CreatorSpec(
            creator_type=typed[0],
            name=typed[1] if len(typed) > 1 else "",
            affiliation=typed[2] if len(typed) > 2 else "",
            email=typed[3] if len(typed) > 3 else "",
            url=typed[4] if len(typed) > 4 else "",
            identifier=identifier,
        )

    parts = _split_untyped(raw, "|" if "|" in raw else ",")
    name = parts[0] if parts else ""
    if not name:
        return None
    return CreatorSpec(
        name=name,
        affiliation=parts[1] if len(parts) > 1 else "",
        identifier=parts[2] if len(parts) > 2 else "",
    )


def _typed_creator_parts(raw: str) -> list[str] | None:
    """Return pipe-delimited creator parts when the first field is a type."""
    if "|" not in raw:
        return None
    parts = _split_untyped(raw, "|")
    if parts and parts[0].lower() in {"person", "organization"}:
        return parts
    return None


def _split_untyped(raw: str, separator: str) -> list[str]:
    """Split a compact creator string and trim each part."""
    return [part.strip() for part in raw.split(separator)]
