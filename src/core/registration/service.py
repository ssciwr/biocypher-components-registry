"""Service helpers for persisted adapter registration submissions."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from src.core.adapter.discovery import (
    AdapterDiscoveryResult,
    discover_local_adapter,
    discover_remote_adapter,
    validate_discovered_adapter,
)
from src.core.adapter.request import AdapterRegistrationRequest
from src.core.adapter.service import create_registration_request
from src.core.registration.errors import (
    ConcurrentRegistrationChangeError,
    DuplicateRegistrationError,
)
from src.core.registration.models import (
    AttemptStatus,
    BatchRefreshSummary,
    ProcessingOutcome,
    RegistrationStatus,
    StoredRegistration,
)
from src.core.registration.store import RegistrationStore
from src.core.shared.errors import (
    InvalidMetadataJSONError,
    MetadataFileNotFoundError,
    MetadataNotFoundError,
    RepositoryUnavailableError,
)
from src.core.shared.ids import slugify_identifier
from src.core.validation.progress import CheckObserver, ValidationProgress
from src.core.validation.results import ValidationDetail

logger = logging.getLogger(__name__)

EVENT_REASONS = {
    "INVALID_SCHEMA": "SCHEMA_INVALID",
    "INVALID_MLCROISSANT": "MLCROISSANT_INVALID",
    "INVALID_BOTH": "VALIDATION_FAILED",
    "REJECTED_SAME_VERSION_CHANGED": "VERSION_NOT_BUMPED",
    "FETCH_FAILED": "REPOSITORY_UNAVAILABLE",
}


def latest_processing_outcome(
    registration: StoredRegistration, store: RegistrationStore
) -> ProcessingOutcome | None:
    """Project terminal events separately from accepted registration state."""
    events = [
        event
        for event in store.list_registration_events(registration.registration_id)
        if event.event_type not in {"SUBMITTED", "REVALIDATED"}
    ]
    if not events:
        return None
    event = max(
        events, key=lambda item: (item.finished_at, item.started_at, item.event_id)
    )
    succeeded = event.event_type in {"VALID_CREATED", "UNCHANGED"}
    return ProcessingOutcome(
        attempt_status=AttemptStatus.SUCCEEDED if succeeded else AttemptStatus.FAILED,
        registration=registration,
        published_version=_published_version(registration),
        update_applied=event.event_type == "VALID_CREATED"
        and any(
            previous.event_type == "VALID_CREATED"
            and previous.event_id != event.event_id
            and previous.finished_at <= event.finished_at
            for previous in events
        ),
        message=event.message
        or ("Metadata accepted." if succeeded else "Processing failed."),
        reason_code=None
        if succeeded
        else EVENT_REASONS.get(event.event_type, event.event_type),
        validation_errors=tuple(event.error_details or ()),
    )


def _published_version(registration: StoredRegistration | None) -> str | None:
    if (
        registration is None
        or not registration.current_registry_entry_id
        or not registration.metadata
    ):
        return None
    return str(registration.metadata.get("version", "")) or None


def register_adapter(
    repository_location: str,
    store: RegistrationStore,
    *,
    on_check: CheckObserver | None = None,
    **fields: Any,
) -> ProcessingOutcome:
    """Validate first; create registration records only when metadata is accepted."""
    request = create_registration_request(
        repository_location=repository_location, **fields
    )
    existing = store.get_registration_by_repository_location(
        request.repository_location
    )
    if existing is not None:
        if existing.current_registry_entry_id is not None:
            raise DuplicateRegistrationError(
                "This repository is already registered. Use Update on its adapter page."
            )
        if existing.submitted_by_github_user_id != request.submitted_by_github_user_id:
            raise PermissionError(
                "Only the submitting account can process this source."
            )
    return _process_candidate(request, store, existing, on_check=on_check)


def update_registration(
    registration_id: str, store: RegistrationStore, *, force_validation: bool = False
) -> ProcessingOutcome:
    """Use the same candidate processor for updates and explicit revalidation."""
    registration = store.get_registration(registration_id)
    if registration is None:
        raise ValueError(f"Registration not found: {registration_id}")
    request = AdapterRegistrationRequest(
        adapter_name=registration.adapter_name,
        adapter_id=registration.adapter_id,
        repository_location=registration.repository_location,
        repository_kind=registration.repository_kind,
        source=registration.repository_location,
        description=registration.description,
        license_value=registration.license_value,
        doi=registration.doi,
        cff_url=registration.cff_url,
        submitted_by_github_user_id=registration.submitted_by_github_user_id,
    )
    return _process_candidate(
        request, store, registration, force_validation=force_validation
    )


def _process_candidate(
    request: AdapterRegistrationRequest,
    store: RegistrationStore,
    registration: StoredRegistration | None,
    *,
    force_validation: bool = False,
    on_check: CheckObserver | None = None,
) -> ProcessingOutcome:
    """Evaluate in memory; only published sources retain failed attempts."""
    processor = _CandidateProcessor(request, store, registration, on_check=on_check)
    return processor.process(force_validation=force_validation)


class _CandidateProcessor:
    """Keep one candidate's discovery, validation, and persistence state together."""

    def __init__(
        self,
        request: AdapterRegistrationRequest,
        store: RegistrationStore,
        registration: StoredRegistration | None,
        *,
        on_check: CheckObserver | None = None,
    ) -> None:
        self.request = request
        self.store = store
        self.registration = registration
        self.started_at = datetime.now(UTC)
        self.previous_version = _published_version(registration)
        self.published = (
            registration is not None
            and registration.current_registry_entry_id is not None
        )
        self.discovered: AdapterDiscoveryResult | None = None
        self.progress = ValidationProgress(
            on_check, include_file=True, include_datasets=True
        )

    def process(self, *, force_validation: bool = False) -> ProcessingOutcome:
        try:
            return self._evaluate(force_validation=force_validation)
        except InvalidMetadataJSONError as exc:
            return self._failure("INVALID_JSON", [str(exc)], _json_syntax_details(exc))
        except (MetadataNotFoundError, MetadataFileNotFoundError) as exc:
            return self._failure("METADATA_NOT_FOUND", [str(exc)])
        except RepositoryUnavailableError as exc:
            return self._failure(exc.reason_code, [str(exc)])
        except DuplicateRegistrationError as exc:
            reason = "VERSION_NOT_BUMPED" if self.published else "DUPLICATE"
            return self._failure(reason, [str(exc)])
        except ConcurrentRegistrationChangeError:
            raise
        except OSError as exc:
            return self._failure("REPOSITORY_UNAVAILABLE", [str(exc)])

    def _evaluate(self, *, force_validation: bool) -> ProcessingOutcome:
        self.progress.update("file", status="RUNNING")
        self.discovered = _discover_registration_metadata(self.request)
        self.progress.update("file", status="PASSED")
        checksum = _metadata_checksum(self.discovered.metadata)
        current = (
            self.store.get_registry_entry(self.registration.current_registry_entry_id)
            if self.published and self.registration
            else None
        )
        unchanged = current is not None and current.metadata_checksum == checksum
        validation_failure = self._validate_candidate(
            unchanged=unchanged, force_validation=force_validation
        )
        if validation_failure is not None:
            return validation_failure
        key = _build_uniqueness_key(
            self.discovered.metadata,
            self.registration.adapter_id
            if self.published and self.registration
            else self.request.adapter_id,
        )
        update_failure = self._check_update(key, unchanged=unchanged)
        if update_failure is not None:
            return update_failure
        profile = (
            self.discovered.validation.profile_version
            if self.discovered.validation
            else current.profile_version
        )
        message = self._success_message(
            str(self.discovered.metadata.get("version", "")), unchanged=unchanged
        )
        stored = self.store.accept_candidate(
            self.request,
            self.discovered.metadata,
            profile or "v1",
            key,
            checksum,
            registration=self.registration,
            started_at=self.started_at,
            message=message,
        )
        version = _published_version(stored)
        return ProcessingOutcome(
            AttemptStatus.SUCCEEDED,
            self._success_message(version, unchanged=unchanged),
            stored,
            version,
            update_applied=self.published and not unchanged,
            profile_version=profile,
            validation_checks=tuple(self.progress.reports),
        )

    def _validate_candidate(
        self, *, unchanged: bool, force_validation: bool
    ) -> ProcessingOutcome | None:
        if unchanged and not force_validation:
            self.progress.stop_unfinished(
                "Metadata is unchanged; validation was not repeated."
            )
            return None
        self.discovered = validate_discovered_adapter(
            self.discovered, progress=self.progress
        )
        validation = self.discovered.validation
        if validation is None:
            raise RuntimeError("Metadata validation did not return a result.")
        if validation.is_valid and not validation.errors:
            return None
        failed = [check.name for check in validation.checks if check.is_valid is False]
        reason = "SCHEMA_INVALID"
        if failed == ["Adapter semantics"]:
            reason = "SEMANTICS_INVALID"
        elif failed == ["Croissant compliance"]:
            reason = "MLCROISSANT_INVALID"
        return self._failure(
            reason, list(validation.errors) or ["Metadata is invalid."]
        )

    def _check_update(self, key: str, *, unchanged: bool) -> ProcessingOutcome | None:
        if not self.published or self.registration is None:
            return None
        if key.split("::", 1)[0] != self.registration.adapter_id:
            return self._failure(
                "ADAPTER_ID_CHANGED",
                ["An update must preserve the registered adapter identity."],
            )
        if not unchanged and key == self.registration.uniqueness_key:
            return self._failure(
                "VERSION_NOT_BUMPED",
                ["Metadata changed for an accepted version. Please bump the version."],
            )
        return None

    def _success_message(self, version: str | None, *, unchanged: bool) -> str:
        if unchanged:
            return "No changes found."
        if self.published:
            return f"Updated from {self.previous_version} to {version}."
        return f"Registered version {version}."

    def _failure(
        self,
        reason: str,
        errors: list[str],
        details: tuple[ValidationDetail, ...] | None = None,
    ) -> ProcessingOutcome:
        stored = self.registration
        message = errors[0] if errors else "Processing failed."
        if self.published and self.registration is not None:
            message += " Previous metadata retained."
            stored = self.store.record_update_failure(
                self.registration.registration_id,
                {value: key for key, value in EVENT_REASONS.items()}.get(
                    reason, reason
                ),
                errors,
                message,
                self.started_at,
            )
        validation = self.discovered.validation if self.discovered else None
        if details is None:
            details = tuple(validation.validation_details) if validation else ()
        if self.progress.reports[0].status == "RUNNING":
            self.progress.update(
                "file",
                status="FAILED",
                reason=reason,
                errors=tuple(errors),
                validation_details=details,
            )
        self.progress.stop_unfinished(
            "An earlier processing step prevented this check from running."
        )
        return ProcessingOutcome(
            AttemptStatus.FAILED,
            message,
            stored if self.published else None,
            published_version=_published_version(stored) if self.published else None,
            reason_code=reason,
            validation_errors=tuple(errors),
            profile_version=validation.profile_version if validation else None,
            validation_details=details,
            validation_checks=tuple(self.progress.reports),
        )


def _json_syntax_details(exc: InvalidMetadataJSONError) -> tuple[ValidationDetail, ...]:
    details = []
    if exc.line is not None:
        details.append(
            ValidationDetail(
                message=str(exc),
                location_description="Correct the JSON syntax at this position.",
                source_file=exc.source_file,
                source_url=exc.source_url,
                line=exc.line,
                column=exc.column,
                location_kind="value",
            )
        )
    return tuple(details)


def submit_registration(
    repository_location: str,
    store: RegistrationStore,
    description: str | None = None,
    license_value: str | None = None,
    doi: str | None = None,
    cff_url: str | None = None,
    submitted_by_github_user_id: str | None = None,
) -> StoredRegistration:
    """Create and persist a registration submission.

    Note on adapter_name: This former property is now always extracted with croissant, and not needed or possible to
    supply here to avoid confusion.

    Args:
        repository_location: Local repository path or remote repository URL.
        store: Persistence backend used to save the submission.
        description: Optional maintainer-facing adapter summary.
        license_value: Optional submitted adapter license text.
        doi: Optional submitted DOI text.
        cff_url: Optional submitted Citation File Format URL.
        submitted_by_github_user_id: GitHub user id for browser submissions.

    Returns:
        The stored registration record with a tracked status.
    """
    request = create_registration_request(
        repository_location=repository_location,
        description=description,
        license_value=license_value,
        doi=doi,
        cff_url=cff_url,
        submitted_by_github_user_id=submitted_by_github_user_id,
    )
    return store.create_registration(request)


VALIDATION_FAILURES = {
    "SCHEMA_INVALID",
    "SEMANTICS_INVALID",
    "MLCROISSANT_INVALID",
    "VALIDATION_FAILED",
    "INVALID_JSON",
}


def finish_registration(
    registration_id: str, store: RegistrationStore
) -> StoredRegistration:
    """Compatibility CLI/API wrapper around the shared candidate processor.

    INVALID describes this returned attempt snapshot. An unaccepted failure is
    not persisted; a published registration retains its accepted state.
    """
    original = store.get_registration(registration_id)
    if original is None:
        raise ValueError(f"Registration not found: {registration_id}")
    outcome = update_registration(registration_id, store)
    return _legacy_attempt_result(outcome, original)


def _legacy_attempt_result(
    outcome: ProcessingOutcome, original: StoredRegistration
) -> StoredRegistration:
    if outcome.attempt_status == AttemptStatus.SUCCEEDED:
        return outcome.registration
    if outcome.reason_code in {"DUPLICATE", "VERSION_NOT_BUMPED"}:
        raise DuplicateRegistrationError(outcome.message)
    if outcome.reason_code not in VALIDATION_FAILURES:
        raise ValueError(outcome.message)
    return replace(
        outcome.registration or original,
        status=RegistrationStatus.INVALID,
        validation_errors=list(outcome.validation_errors),
        profile_version=outcome.profile_version,
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
            previous = store.get_registration(registration_id)
            outcome = update_registration(registration_id, store)
        except Exception:
            logger.exception(
                "Batch processing failed for registration %s", registration_id
            )
            counts["fetch_failed"] += 1
            continue
        if outcome.attempt_status == AttemptStatus.SUCCEEDED:
            bucket = (
                "unchanged"
                if previous.current_registry_entry_id and not outcome.update_applied
                else "valid_created"
            )
        elif outcome.reason_code == "DUPLICATE":
            bucket = "duplicate"
        elif outcome.reason_code == "VERSION_NOT_BUMPED":
            bucket = "rejected_same_version_changed"
        elif outcome.reason_code in VALIDATION_FAILURES:
            bucket = "invalid"
        else:
            bucket = "fetch_failed"
        counts[bucket] += 1

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
    registration_id: str, store: RegistrationStore
) -> StoredRegistration:
    """Retry staged sources or the latest failed update with full validation."""
    registration = store.get_registration(registration_id)
    if registration is None:
        raise ValueError(f"Registration not found: {registration_id}")
    latest = latest_processing_outcome(registration, store)
    if registration.current_registry_entry_id:
        if latest is not None and latest.attempt_status == AttemptStatus.SUCCEEDED:
            raise ValueError(
                "On-demand revalidation is only available for INVALID or FETCH_FAILED registrations."
            )
        store.record_revalidation_requested(registration_id)
    outcome = update_registration(registration_id, store, force_validation=True)
    return _legacy_attempt_result(outcome, registration)


def _discover_registration_metadata(
    registration: StoredRegistration | AdapterRegistrationRequest,
) -> AdapterDiscoveryResult:
    """Load croissant metadata for one stored registration."""
    if registration.repository_kind == "remote":
        return discover_remote_adapter(registration.repository_location)
    return discover_local_adapter(registration.repository_location)


def _build_uniqueness_key(
    metadata: dict[str, Any],
    fallback_adapter_id: str | None = None,
) -> str:
    """Build the configured uniqueness key for duplicate detection."""
    adapter_id = _resolve_adapter_id(metadata, fallback_adapter_id)
    version = str(metadata.get("version", "")).strip()
    if not adapter_id or not version:
        raise ValueError("Registration uniqueness key requires adapter id and version.")
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


def _metadata_checksum(metadata: dict[str, Any]) -> str:
    """Compute a stable checksum for one metadata payload."""
    canonical = json.dumps(metadata, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
