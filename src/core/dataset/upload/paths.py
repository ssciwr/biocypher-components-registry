"""Path validation for browser-provided dataset inventories."""

from __future__ import annotations

import re
import unicodedata
from pathlib import PurePosixPath

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")


def normalize_relative_path(value: str) -> str:
    """Return a safe NFC-normalized POSIX path below the selected source root."""
    normalized = unicodedata.normalize("NFC", value.strip())
    if not normalized or normalized in {".", ".."}:
        raise ValueError("Dataset paths must identify a file below the source root.")
    if "\\" in normalized or _CONTROL_CHARACTERS.search(normalized):
        raise ValueError("Dataset paths contain unsupported characters.")

    path = PurePosixPath(normalized)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("Dataset paths must be safe root-relative POSIX paths.")
    if len(normalized.encode("utf-8")) > 1_024:
        raise ValueError("Dataset paths must not exceed 1024 UTF-8 bytes.")
    if any(len(part.encode("utf-8")) > 255 for part in path.parts):
        raise ValueError("Dataset path components must not exceed 255 UTF-8 bytes.")
    return path.as_posix()


def validate_unique_paths(paths: list[str]) -> list[str]:
    """Normalize paths and reject exact or case-folded collisions."""
    normalized_paths: list[str] = []
    seen: set[str] = set()
    seen_casefolded: set[str] = set()
    for value in paths:
        normalized = normalize_relative_path(value)
        folded = normalized.casefold()
        if normalized in seen or folded in seen_casefolded:
            raise ValueError(f"Dataset path collision: {normalized}")
        seen.add(normalized)
        seen_casefolded.add(folded)
        normalized_paths.append(normalized)
    return normalized_paths
