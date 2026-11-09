"""Restore original source identity after generation from transient artifacts."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from src.core.dataset.upload.errors import UploadSessionError
from src.core.dataset.upload.limits import MAX_GENERATED_JSON_BYTES
from src.core.dataset.upload.models import UploadInventoryEntry, UploadSession
from src.core.dataset.upload.paths import normalize_relative_path
from src.core.shared.constants import (
    CROISSANT_1_0_CONTEXT,
    CROISSANT_CONFORMS_TO_URL,
)

_FILE_OBJECT_TYPES = {"FileObject", "cr:FileObject"}
_INLINE_SAMPLE_KEYS = {
    "examples",
    "sample",
    "samples",
    "sampleValues",
}
_SAMPLE_COUNT_KEYS = {
    "rowCount",
    "recordCount",
    "numberOfRecords",
}
_INTERNAL_FILE_KEYS = {
    "entryId",
    "artifactMode",
    "artifactSha256",
    "artifact_sha256",
    "strategy",
}


def reconcile_generated_metadata(
    document: dict[str, Any], session: UploadSession
) -> dict[str, Any]:
    """Reconcile every generated FileObject with exactly one original entry."""
    reconciled = deepcopy(document)
    reconciled["@context"] = deepcopy(CROISSANT_1_0_CONTEXT)
    reconciled["conformsTo"] = CROISSANT_CONFORMS_TO_URL
    file_objects = _file_objects(reconciled)
    if len(file_objects) != len(session.entries):
        raise UploadSessionError(
            "Generated metadata does not describe every source file exactly once."
        )

    unmatched = dict(session.entries)
    for file_object in file_objects:
        entry = _match_entry(file_object, unmatched)
        unmatched.pop(entry.entry_id)
        file_object["name"] = Path(entry.relative_path).name
        file_object["contentUrl"] = entry.content_url or entry.relative_path
        file_object["contentSize"] = str(entry.original_size)
        file_object["sha256"] = entry.original_sha256
        logical_encoding = (
            "text/csv" if entry.logical_format == "csv" else "text/tab-separated-values"
        )
        file_object["encodingFormat"] = (
            [logical_encoding, "application/gzip"]
            if entry.compression == "gzip"
            else logical_encoding
        )
        for key in _INTERNAL_FILE_KEYS:
            file_object.pop(key, None)

    if unmatched:
        raise UploadSessionError("Generated metadata reconciliation is incomplete.")
    _remove_sample_only_values(
        reconciled,
        remove_counts=any(
            entry.artifact_mode == "sample" for entry in session.entries.values()
        ),
    )
    _remove_private_values(reconciled, scratch=str(session.root))
    _validate_private_values(reconciled, session)
    encoded = json.dumps(reconciled, ensure_ascii=False).encode("utf-8")
    if len(encoded) > MAX_GENERATED_JSON_BYTES:
        raise UploadSessionError("Generated metadata exceeds the response size limit.")
    return reconciled


def _file_objects(document: dict[str, Any]) -> list[dict[str, Any]]:
    distribution = document.get("distribution")
    if isinstance(distribution, dict):
        candidates = [distribution]
    elif isinstance(distribution, list):
        candidates = [item for item in distribution if isinstance(item, dict)]
    else:
        candidates = []
    return [item for item in candidates if _is_file_object(item)]


def _is_file_object(item: dict[str, Any]) -> bool:
    item_type = item.get("@type")
    if isinstance(item_type, list):
        return any(value in _FILE_OBJECT_TYPES for value in item_type)
    return item_type in _FILE_OBJECT_TYPES


def _match_entry(
    file_object: dict[str, Any], unmatched: dict[str, UploadInventoryEntry]
) -> UploadInventoryEntry:
    identity_values = [
        str(file_object.get("entryId") or ""),
        str(file_object.get("contentUrl") or ""),
        str(file_object.get("name") or ""),
        str(file_object.get("@id") or ""),
    ]
    for identity in identity_values:
        if identity in unmatched:
            return unmatched[identity]

    normalized_candidates: set[str] = set()
    for identity in identity_values[1:]:
        candidate = _candidate_path(identity)
        if candidate:
            normalized_candidates.add(candidate)
    exact = [
        entry
        for entry in unmatched.values()
        if entry.relative_path in normalized_candidates
    ]
    if len(exact) == 1:
        return exact[0]

    basename_candidates = {Path(value).name for value in normalized_candidates}
    by_basename = [
        entry
        for entry in unmatched.values()
        if Path(entry.relative_path).name in basename_candidates
    ]
    if len(by_basename) == 1:
        return by_basename[0]
    raise UploadSessionError("A generated FileObject cannot be matched unambiguously.")


def _candidate_path(value: str) -> str | None:
    if not value:
        return None
    parsed = urlparse(value)
    raw_path = unquote(parsed.path if parsed.scheme else value).lstrip("./")
    try:
        return normalize_relative_path(raw_path)
    except ValueError:
        return None


def _remove_sample_only_values(
    value: Any, *, remove_counts: bool, in_context: bool = False
) -> None:
    if isinstance(value, dict):
        for key in value.copy():
            if not in_context and (
                key in _INLINE_SAMPLE_KEYS
                or (remove_counts and key in _SAMPLE_COUNT_KEYS)
            ):
                del value[key]
                continue
            _remove_sample_only_values(
                value[key],
                remove_counts=remove_counts,
                in_context=in_context or key == "@context",
            )
    elif isinstance(value, list):
        for item in value:
            _remove_sample_only_values(
                item, remove_counts=remove_counts, in_context=in_context
            )


def _remove_private_values(value: Any, *, scratch: str) -> None:
    """Delete generator-created scratch and inline-data values before validation."""
    if isinstance(value, dict):
        for key in value.copy():
            nested = value[key]
            if isinstance(nested, str) and _is_private_value(nested, scratch):
                del value[key]
                continue
            _remove_private_values(nested, scratch=scratch)
    elif isinstance(value, list):
        value[:] = [
            item
            for item in value
            if not (isinstance(item, str) and _is_private_value(item, scratch))
        ]
        for item in value:
            _remove_private_values(item, scratch=scratch)


def _is_private_value(value: str, scratch: str) -> bool:
    return scratch in value or value.startswith(("file:", "data:"))


def _validate_private_values(document: dict[str, Any], session: UploadSession) -> None:
    artifact_hashes = {
        entry.artifact_sha256
        for entry in session.entries.values()
        if entry.artifact_sha256 and entry.artifact_sha256 != entry.original_sha256
    }
    scratch = str(session.root)
    _ensure_public_value(document, scratch=scratch, artifact_hashes=artifact_hashes)


def _ensure_public_value(
    value: Any, *, scratch: str, artifact_hashes: set[str]
) -> None:
    """Reject private values anywhere in a generated metadata tree."""
    if isinstance(value, dict):
        nested_values = value.values()
    elif isinstance(value, list):
        nested_values = value
    else:
        _ensure_public_string(value, scratch=scratch, artifact_hashes=artifact_hashes)
        return

    for nested in nested_values:
        _ensure_public_value(
            nested, scratch=scratch, artifact_hashes=artifact_hashes
        )


def _ensure_public_string(
    value: Any, *, scratch: str, artifact_hashes: set[str]
) -> None:
    """Reject one scratch URL, inline value, or transient artifact hash."""
    if not isinstance(value, str):
        return
    if _is_private_value(value, scratch):
        raise UploadSessionError(
            "Generated metadata contains a private scratch value."
        )
    if value in artifact_hashes:
        raise UploadSessionError(
            "Generated metadata contains an artifact identity."
        )
