"""Framework-independent adapter identity and entry selection."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.shared.ids import slugify_identifier

if TYPE_CHECKING:
    from src.core.registration.models import RegistryEntry


def adapter_id_from_uniqueness_key(uniqueness_key: str) -> str:
    """Extract the public adapter identity."""
    return uniqueness_key.split("::", maxsplit=1)[0]


def canonical_adapter_id(metadata: dict, fallback: str | None = None) -> str:
    """Use explicit JSON-LD identity, otherwise the canonical metadata name."""
    for value in (metadata.get("@id"), metadata.get("name"), fallback):
        if isinstance(value, str) and value.strip():
            return slugify_identifier(value.strip()).replace("::", "-")
    return ""


def latest_registry_entry(entries: list[RegistryEntry]) -> RegistryEntry:
    """Select the most recently updated published entry."""
    return max(entries, key=lambda entry: (entry.updated_at, entry.created_at))
