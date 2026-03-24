"""Service helpers for persisted adapter registration submissions."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from dataclasses import replace
from typing import Any

from src.core.adapter.discovery import (
    AdapterDiscoveryResult,
    discover_local_adapter,
    discover_remote_adapter,
    validate_discovered_adapter,
)
from src.core.adapter.service import create_registration_request
from src.core.registration.errors import DuplicateRegistrationError
from src.core.registration.models import (
    BatchRefreshSummary,
    RegistrationStatus,
    StoredRegistration,
)
from src.core.registration.store import RegistrationStore
from src.core.shared.errors import MetadataDiscoveryError
from src.core.shared.ids import slugify_identifier


def submit_registration(
    adapter_name: str,
    repository_location: str,
    store: RegistrationStore,
    contact_email: str | None = None,
) -> StoredRegistration:
    """Create and persist a registration submission.

    Args:
        adapter_name: Human-readable adapter name provided by the maintainer.
        repository_location: Local repository path or supported repository URL.
        store: Persistence backend used to save the submission.
        contact_email: Optional maintainer contact email for status follow-up.

    Returns:
        The stored registration record with a tracked status.
    """
    request = create_registration_request(
        adapter_name=adapter_name,
        repository_location=repository_location,
        contact_email=contact_email,
    )
    return store.create_registration(request)


def finish_registration(
    registration_id: str,
    store: RegistrationStore,
) -> StoredRegistration:
    """Discover, validate, and persist one stored registration result.

    Args:
        registration_id: Identifier of the stored submission to process.
        store: Persistence backend used to load and update the submission.

    Returns:
        The updated registration record marked as ``VALID`` or ``INVALID``.

    Raises:
        ValueError: If the registration does not exist or discovery fails before validation.
    """
    registration = store.get_registration(registration_id)
    if registration is None:
        raise ValueError(f"Registration not found: {registration_id}")

    discovered = _discover_registration_metadata(registration)
    observed_checksum = _metadata_checksum(discovered.metadata)
    discovered = validate_discovered_adapter(discovered)
    if discovered.validation is None:
        raise ValueError("Registration validation did not produce a validation result.")

    validation_errors = list(discovered.validation.errors)
    if discovered.validation.is_valid is False or validation_errors:
        event_type, mlcroissant_valid, schema_valid = _classify_invalid_outcome(
            discovered.validation.checks,
        )
        stored = store.mark_registration_invalid(
            registration_id=registration.registration_id,
            errors=validation_errors or ["Adapter metadata is invalid."],
            profile_version=discovered.validation.profile_version,
            metadata=discovered.metadata,
            metadata_path=str(discovered.metadata_path) if discovered.metadata_path else None,
            event_type=event_type,
            mlcroissant_valid=mlcroissant_valid,
            schema_valid=schema_valid,
            observed_checksum=observed_checksum,
        )
        return replace(
            stored,
            metadata_path=str(discovered.metadata_path) if discovered.metadata_path else None,
        )

    stored = store.mark_registration_valid(
        registration_id=registration.registration_id,
        metadata=discovered.metadata,
        metadata_path=str(discovered.metadata_path) if discovered.metadata_path else None,
        profile_version=discovered.validation.profile_version,
        uniqueness_key=_build_uniqueness_key(
            discovered.metadata,
            fallback_adapter_id=registration.adapter_id,
        ),
        observed_checksum=observed_checksum,
    )

    return replace(
        stored,
        metadata_path=str(discovered.metadata_path) if discovered.metadata_path else None,
    )


def refresh_active_registrations(
    store: RegistrationStore,
) -> BatchRefreshSummary:
    """Process every active registration source without stopping on per-source failures."""
    started_at = datetime.now(UTC)
    registration_ids = store.list_active_registration_ids()
    counts = {
        "valid_created": 0,
        "unchanged": 0,
        "invalid": 0,
        "duplicate": 0,
        "rejected_same_version_changed": 0,
        "fetch_failed": 0,
    }

    for registration_id in registration_ids:
        try:
            processed = finish_registration(registration_id, store)
        except DuplicateRegistrationError:
            latest_event_type = store.get_latest_event_type(registration_id)
            _increment_summary_count(counts, latest_event_type)
            continue
        except Exception as exc:  # noqa: BLE001
            store.mark_registration_fetch_failed(
                registration_id=registration_id,
                error_message=str(exc),
            )
            counts["fetch_failed"] += 1
            continue

        latest_event_type = store.get_latest_event_type(registration_id)
        if processed.status == RegistrationStatus.INVALID:
            counts["invalid"] += 1
            continue
        _increment_summary_count(counts, latest_event_type)

    summary = BatchRefreshSummary(
        active_sources=len(registration_ids),
        processed=len(registration_ids),
        valid_created=counts["valid_created"],
        unchanged=counts["unchanged"],
        invalid=counts["invalid"],
        duplicate=counts["duplicate"],
        rejected_same_version_changed=counts["rejected_same_version_changed"],
        fetch_failed=counts["fetch_failed"],
    )
    store.record_batch_refresh(
        summary,
        started_at=started_at,
        finished_at=datetime.now(UTC),
    )
    return summary


def revalidate_registration(
    registration_id: str,
    store: RegistrationStore,
) -> StoredRegistration:
    """Reprocess one previously failing source immediately on demand."""
    registration = store.get_registration(registration_id)
    if registration is None:
        raise ValueError(f"Registration not found: {registration_id}")

    latest_event_type = store.get_latest_event_type(registration_id)
    if (
        registration.status != RegistrationStatus.INVALID
        and latest_event_type != "FETCH_FAILED"
    ):
        raise ValueError(
            "On-demand revalidation is only available for INVALID or FETCH_FAILED registrations."
        )

    store.record_revalidation_requested(registration_id)
    try:
        return finish_registration(registration_id, store)
    except DuplicateRegistrationError:
        raise
    except (FileNotFoundError, OSError, MetadataDiscoveryError) as exc:
        store.mark_registration_fetch_failed(
            registration_id=registration_id,
            error_message=str(exc),
        )
        raise ValueError(str(exc)) from exc


def _discover_registration_metadata(
    registration: StoredRegistration,
) -> AdapterDiscoveryResult:
    """Load croissant metadata for one stored registration."""
    if registration.repository_kind == "remote":
        return discover_remote_adapter(registration.repository_location)
    return discover_local_adapter(registration.repository_location)


def _increment_summary_count(counts: dict[str, int], event_type: str | None) -> None:
    """Increment the correct batch summary bucket for one recorded event type."""
    if event_type == "VALID_CREATED":
        counts["valid_created"] += 1
        return
    if event_type == "UNCHANGED":
        counts["unchanged"] += 1
        return
    if event_type == "DUPLICATE":
        counts["duplicate"] += 1
        return
    if event_type == "REJECTED_SAME_VERSION_CHANGED":
        counts["rejected_same_version_changed"] += 1
        return
    if event_type == "FETCH_FAILED":
        counts["fetch_failed"] += 1


def _build_uniqueness_key(
    metadata: dict[str, Any],
    fallback_adapter_id: str | None = None,
) -> str:
    """Build the configured uniqueness key for duplicate detection."""
    adapter_id = _resolve_adapter_id(metadata, fallback_adapter_id)
    version = str(metadata.get("version", "")).strip()
    if not adapter_id or not version:
        raise ValueError(
            "Registration uniqueness key requires adapter id and version."
        )
    return f"{adapter_id}::{version}"


def _resolve_adapter_id(
    metadata: dict[str, Any],
    fallback_adapter_id: str | None = None,
) -> str:
    """Resolve a stable adapter identifier for duplicate detection."""
    metadata_adapter_id = str(metadata.get("@id", "")).strip()
    if metadata_adapter_id:
        return slugify_identifier(metadata_adapter_id)

    if fallback_adapter_id:
        return slugify_identifier(fallback_adapter_id)

    metadata_name = str(metadata.get("name", "")).strip()
    if metadata_name:
        return slugify_identifier(metadata_name)

    return ""


def _classify_invalid_outcome(
    checks: list[Any],
) -> tuple[str, bool | None, bool | None]:
    """Classify one invalid validation outcome into a registration event type."""
    mlcroissant_valid: bool | None = None
    schema_valid = True

    for check in checks:
        name = str(getattr(check, "name", ""))
        is_valid = getattr(check, "is_valid", None)
        if name == "Croissant compliance":
            mlcroissant_valid = is_valid
            continue
        if name.startswith("Embedded dataset:") and is_valid is False:
            schema_valid = False
            continue
        if is_valid is False:
            schema_valid = False

    if mlcroissant_valid is False and schema_valid is False:
        return "INVALID_BOTH", mlcroissant_valid, schema_valid
    if mlcroissant_valid is False:
        return "INVALID_MLCROISSANT", mlcroissant_valid, schema_valid
    return "INVALID_SCHEMA", mlcroissant_valid, schema_valid


def _metadata_checksum(metadata: dict[str, Any]) -> str:
    """Compute a stable checksum for one metadata payload."""
    canonical = json.dumps(metadata, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
