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
        return _dataset_creator_from_typed(typed)
    parts = _split_untyped(raw, "|" if "|" in raw else ",")
    return _dataset_creator_from_untyped(parts)


def parse_adapter_creator_string(raw: str) -> CreatorSpec | None:
    """Parse an adapter creator string into structured fields.

    Args:
        raw: Creator text from CLI or configuration input.

    Returns:
        A parsed creator spec, or ``None`` when no usable name is present.
    """
    typed = _typed_creator_parts(raw)
    if typed is not None:
        return _adapter_creator_from_typed(typed)
    parts = _split_untyped(raw, "|" if "|" in raw else ",")
    return _adapter_creator_from_untyped(parts)


def _part(parts: list[str], index: int, default: str = "") -> str:
    """Return the part at ``index``, or ``default`` when it is not present."""
    return parts[index] if len(parts) > index else default


def _dataset_creator_from_typed(typed: list[str]) -> CreatorSpec:
    """Build a dataset ``CreatorSpec`` from pipe-delimited typed parts."""
    return CreatorSpec(
        creator_type=typed[0],
        name=_part(typed, 1),
        affiliation=_part(typed, 2),
        email=_part(typed, 3),
        url=_part(typed, 4),
        identifier=_part(typed, 5),
    )


def _dataset_creator_from_untyped(parts: list[str]) -> CreatorSpec | None:
    """Build a dataset ``CreatorSpec`` from untyped comma/pipe-delimited parts."""
    name = _part(parts, 0)
    if not name:
        return None
    return CreatorSpec(
        name=name,
        email=_part(parts, 1),
        url=_part(parts, 2),
    )


def _adapter_creator_from_typed(typed: list[str]) -> CreatorSpec:
    """Build an adapter ``CreatorSpec`` from pipe-delimited typed parts."""
    identifier = typed[5] if len(typed) > 5 else _part(typed, 4)
    return CreatorSpec(
        creator_type=typed[0],
        name=_part(typed, 1),
        affiliation=_part(typed, 2),
        email=_part(typed, 3),
        url=_part(typed, 4),
        identifier=identifier,
    )


def _adapter_creator_from_untyped(parts: list[str]) -> CreatorSpec | None:
    """Build an adapter ``CreatorSpec`` from untyped comma/pipe-delimited parts."""
    name = _part(parts, 0)
    if not name:
        return None
    return CreatorSpec(
        name=name,
        affiliation=_part(parts, 1),
        identifier=_part(parts, 2),
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
