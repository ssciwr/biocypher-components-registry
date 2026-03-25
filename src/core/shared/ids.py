"""Helpers for building stable identifiers from user-provided text."""

from __future__ import annotations


def slugify_identifier(text: str) -> str:
    """Normalize free-text input into a simple slug identifier.

    Args:
        text: Raw text to normalize.

    Returns:
        A lowercase identifier with common separators replaced by hyphens.
    """
    return (
        str(text or "")
        .strip()
        .lower()
        .replace(" ", "-")
        .replace("_", "-")
        .replace("/", "-")
    )
