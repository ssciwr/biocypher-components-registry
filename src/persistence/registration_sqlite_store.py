"""SQLAlchemy-backed SQLite storage for adapter registration requests."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, insert, select, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import IntegrityError

from src.core.adapter.request import AdapterRegistrationRequest
from src.core.registration.errors import DuplicateRegistrationError
from src.core.registration.models import (
    BatchRefreshRecord,
    BatchRefreshSummary,
    RegistrationEvent,
    RegistryEntry,
    RegistrationStatus,
    StoredRegistration,
)
from src.persistence.tables import (
    metadata,
    registration_events_table,
    registration_sources_table,
    registry_entries_table,
    registry_refreshes_table,
)
from src.core.shared.files import fetch_local_metadata
from src.core.shared.ids import slugify_identifier


class SQLiteRegistrationStore:
    """Persist registration requests in SQLite through SQLAlchemy Core."""

    def __init__(self, database_path: str | Path) -> None:
        """Create a store that reads and writes registrations to SQLite."""
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = self._build_engine()
        self._initialize_database()

    def create_registration(
        self,
        request: AdapterRegistrationRequest,
    ) -> StoredRegistration:
        """Insert a registration request and return the stored record."""
        registration = StoredRegistration(
            registration_id=str(uuid4()),
            adapter_name=request.adapter_name,
            adapter_id=request.adapter_id,
            repository_location=request.repository_location,
            repository_kind=request.repository_kind,
            status=RegistrationStatus.SUBMITTED,
            created_at=datetime.now(UTC),
            contact_email=request.contact_email,
        )

        with self.engine.begin() as connection:
            connection.execute(
                insert(registration_sources_table).values(
                    id=registration.registration_id,
                    submitted_adapter_name=registration.adapter_name,
                    repository_location=registration.repository_location,
                    source_kind=registration.repository_kind,
                    contact_email=registration.contact_email,
                    is_active=True,
                    created_at=registration.created_at.isoformat(),
                    updated_at=registration.created_at.isoformat(),
                    last_checked_at=None,
                    last_seen_at=None,
                    current_registry_entry_id=None,
                )
            )
            self._insert_registration_event(
                connection,
                source_id=registration.registration_id,
                registry_entry_id=None,
                event_type="SUBMITTED",
                profile_version=None,
                metadata_json=None,
                error_details=None,
                message="Registration submitted.",
                started_at=registration.created_at.isoformat(),
                finished_at=registration.created_at.isoformat(),
            )

        return registration

    def get_registration(self, registration_id: str) -> StoredRegistration | None:
        """Return one stored registration by identifier when it exists."""
        with self.engine.connect() as connection:
            source_row = self._source_row(connection, registration_id)
            if source_row is None:
                return None
            current_entry = self._current_registry_entry(connection, registration_id)
            latest_event = self._latest_event_for_source(connection, registration_id)

        return self._source_to_registration(source_row, current_entry, latest_event)

    def list_active_registration_ids(self) -> list[str]:
        """Return all active registration identifiers in stable creation order."""
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(registration_sources_table.c.id)
                .where(registration_sources_table.c.is_active.is_(True))
                .order_by(
                    registration_sources_table.c.created_at,
                    registration_sources_table.c.id,
                )
            ).all()

        return [str(row[0]) for row in rows]

    def list_active_registrations(self) -> list[StoredRegistration]:
        """Return all active registrations in stable creation order."""
        return [
            registration
            for registration_id in self.list_active_registration_ids()
            if (registration := self.get_registration(registration_id)) is not None
        ]

    def get_latest_event_type(self, registration_id: str) -> str | None:
        """Return the latest event type for one registration when it exists."""
        with self.engine.connect() as connection:
            row = self._latest_event_for_source(connection, registration_id)
        if row is None:
            return None
        return str(row["event_type"])

    def list_registration_events(self, registration_id: str) -> list[RegistrationEvent]:
        """Return event history for one registration in chronological order."""
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(registration_events_table)
                .where(registration_events_table.c.source_id == registration_id)
                .order_by(
                    registration_events_table.c.started_at,
                    registration_events_table.c.finished_at,
                    registration_events_table.c.id,
                )
            ).mappings().all()

        return [self._event_row_to_event(row) for row in rows]

    def list_registry_entries(self) -> list[RegistryEntry]:
        """Return active canonical registry entries in stable creation order."""
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(registry_entries_table)
                .where(registry_entries_table.c.is_active.is_(True))
                .order_by(
                    registry_entries_table.c.created_at,
                    registry_entries_table.c.id,
                )
            ).mappings().all()

        return [self._registry_entry_row_to_entry(row) for row in rows]

    def get_registry_entry(self, entry_id: str) -> RegistryEntry | None:
        """Return one active canonical registry entry by identifier when it exists."""
        with self.engine.connect() as connection:
            row = connection.execute(
                select(registry_entries_table).where(
                    registry_entries_table.c.id == entry_id,
                    registry_entries_table.c.is_active.is_(True),
                )
            ).mappings().first()

        if row is None:
            return None
        return self._registry_entry_row_to_entry(row)

    def record_batch_refresh(
        self,
        summary: BatchRefreshSummary,
        started_at: datetime,
        finished_at: datetime,
    ) -> BatchRefreshRecord:
        """Persist one batch refresh summary."""
        refresh_id = str(uuid4())
        with self.engine.begin() as connection:
            connection.execute(
                insert(registry_refreshes_table).values(
                    id=refresh_id,
                    started_at=started_at.isoformat(),
                    finished_at=finished_at.isoformat(),
                    active_sources=summary.active_sources,
                    processed=summary.processed,
                    valid_created=summary.valid_created,
                    unchanged=summary.unchanged,
                    invalid=summary.invalid,
                    duplicate=summary.duplicate,
                    rejected_same_version_changed=summary.rejected_same_version_changed,
                    fetch_failed=summary.fetch_failed,
                )
            )

        return BatchRefreshRecord(
            refresh_id=refresh_id,
            started_at=started_at,
            finished_at=finished_at,
            active_sources=summary.active_sources,
            processed=summary.processed,
            valid_created=summary.valid_created,
            unchanged=summary.unchanged,
            invalid=summary.invalid,
            duplicate=summary.duplicate,
            rejected_same_version_changed=summary.rejected_same_version_changed,
            fetch_failed=summary.fetch_failed,
        )

    def get_latest_batch_refresh(self) -> BatchRefreshRecord | None:
        """Return the most recent batch refresh summary when one exists."""
        with self.engine.connect() as connection:
            row = connection.execute(
                select(registry_refreshes_table).order_by(
                    registry_refreshes_table.c.finished_at.desc(),
                    registry_refreshes_table.c.started_at.desc(),
                    registry_refreshes_table.c.id.desc(),
                )
            ).mappings().first()

        if row is None:
            return None
        return self._refresh_row_to_record(row)

    def mark_registration_valid(
        self,
        registration_id: str,
        metadata: dict[str, object],
        metadata_path: str | None,
        profile_version: str,
        uniqueness_key: str,
        observed_checksum: str,
    ) -> StoredRegistration:
        """Persist approved metadata and update the registration status."""
        updated_at = datetime.now(UTC)
        metadata_payload = json.dumps(metadata, sort_keys=True)
        adapter_name = str(metadata.get("name", "")).strip()
        adapter_version = str(metadata.get("version", "")).strip()
        pending_duplicate_error: str | None = None

        try:
            with self.engine.begin() as connection:
                current_entry = self._current_registry_entry(connection, registration_id)
                if (
                    current_entry is not None
                    and str(current_entry["metadata_checksum"] or "") == observed_checksum
                ):
                    connection.execute(
                        update(registration_sources_table)
                        .where(registration_sources_table.c.id == registration_id)
                        .values(
                            updated_at=updated_at.isoformat(),
                            last_checked_at=updated_at.isoformat(),
                            last_seen_at=updated_at.isoformat(),
                        )
                    )
                    self._insert_registration_event(
                        connection,
                        source_id=registration_id,
                        registry_entry_id=str(current_entry["id"]),
                        event_type="UNCHANGED",
                        profile_version=profile_version,
                        metadata_json=metadata_payload,
                        error_details=None,
                        message="Metadata checksum unchanged; canonical entry preserved.",
                        started_at=updated_at.isoformat(),
                        finished_at=updated_at.isoformat(),
                        mlcroissant_valid=True,
                        schema_valid=True,
                        observed_checksum=observed_checksum,
                    )
                    updated_registration = self.get_registration(registration_id)
                    if updated_registration is None:
                        raise ValueError(f"Registration not found: {registration_id}")
                    return replace(updated_registration, metadata_path=metadata_path)

                existing_entry = self._registry_entry_by_uniqueness_key(
                    connection,
                    uniqueness_key,
                )
                if existing_entry is not None:
                    event_type = (
                        "DUPLICATE"
                        if str(existing_entry["metadata_checksum"] or "") == observed_checksum
                        else "REJECTED_SAME_VERSION_CHANGED"
                    )
                    message = (
                        "Duplicate canonical registry entry rejected."
                        if event_type == "DUPLICATE"
                        else "Changed metadata for the same adapter_id and version was rejected."
                    )
                    error_message = (
                        f"Duplicate registration rejected for uniqueness key: {uniqueness_key}"
                        if event_type == "DUPLICATE"
                        else (
                            "Registration rejected because metadata changed for an existing "
                            f"adapter_id and version: {uniqueness_key}. Please bump the version."
                        )
                    )
                    connection.execute(
                        update(registration_sources_table)
                        .where(registration_sources_table.c.id == registration_id)
                        .values(
                            updated_at=updated_at.isoformat(),
                            last_checked_at=updated_at.isoformat(),
                            last_seen_at=updated_at.isoformat(),
                        )
                    )
                    self._insert_registration_event(
                        connection,
                        source_id=registration_id,
                        registry_entry_id=str(existing_entry["id"]),
                        event_type=event_type,
                        profile_version=profile_version,
                        metadata_json=metadata_payload,
                        error_details=json.dumps([error_message]),
                        message=message,
                        started_at=updated_at.isoformat(),
                        finished_at=updated_at.isoformat(),
                        observed_checksum=observed_checksum,
                    )
                    pending_duplicate_error = error_message
                else:
                    registry_entry_id = str(uuid4())
                    connection.execute(
                        insert(registry_entries_table).values(
                            id=registry_entry_id,
                            source_id=registration_id,
                            adapter_name=adapter_name,
                            adapter_version=adapter_version,
                            profile_version=profile_version,
                            uniqueness_key=uniqueness_key,
                            metadata_checksum=observed_checksum,
                            metadata_json=metadata_payload,
                            created_at=updated_at.isoformat(),
                            updated_at=updated_at.isoformat(),
                            is_active=True,
                        )
                    )
                    connection.execute(
                        update(registration_sources_table)
                        .where(registration_sources_table.c.id == registration_id)
                        .values(
                            updated_at=updated_at.isoformat(),
                            last_checked_at=updated_at.isoformat(),
                            last_seen_at=updated_at.isoformat(),
                            current_registry_entry_id=registry_entry_id,
                        )
                    )
                    self._insert_registration_event(
                        connection,
                        source_id=registration_id,
                        registry_entry_id=registry_entry_id,
                        event_type="VALID_CREATED",
                        profile_version=profile_version,
                        metadata_json=metadata_payload,
                        error_details=None,
                        message="Canonical valid registry entry created.",
                        started_at=updated_at.isoformat(),
                        finished_at=updated_at.isoformat(),
                        mlcroissant_valid=True,
                        schema_valid=True,
                        observed_checksum=observed_checksum,
                    )
        except IntegrityError as exc:
            raise DuplicateRegistrationError(
                f"Duplicate registration rejected for uniqueness key: {uniqueness_key}"
            ) from exc

        updated_registration = self.get_registration(registration_id)
        if updated_registration is None:
            raise ValueError(f"Registration not found: {registration_id}")
        if pending_duplicate_error is not None:
            raise DuplicateRegistrationError(pending_duplicate_error)
        return replace(updated_registration, metadata_path=metadata_path)

    def mark_registration_invalid(
        self,
        registration_id: str,
        errors: list[str],
        profile_version: str | None,
        metadata: dict[str, object] | None = None,
        metadata_path: str | None = None,
        event_type: str = "INVALID_SCHEMA",
        mlcroissant_valid: bool | None = None,
        schema_valid: bool | None = None,
        observed_checksum: str | None = None,
    ) -> StoredRegistration:
        """Persist failed validation details and update the registration status."""
        updated_at = datetime.now(UTC)
        error_payload = json.dumps(errors)
        metadata_payload = (
            json.dumps(metadata, sort_keys=True) if metadata is not None else None
        )

        with self.engine.begin() as connection:
            connection.execute(
                update(registration_sources_table)
                .where(registration_sources_table.c.id == registration_id)
                .values(
                    updated_at=updated_at.isoformat(),
                    last_checked_at=updated_at.isoformat(),
                    last_seen_at=updated_at.isoformat(),
                )
            )
            self._insert_registration_event(
                connection,
                source_id=registration_id,
                registry_entry_id=None,
                event_type=event_type,
                profile_version=profile_version,
                metadata_json=metadata_payload,
                error_details=error_payload,
                message="Registration failed validation.",
                started_at=updated_at.isoformat(),
                finished_at=updated_at.isoformat(),
                mlcroissant_valid=mlcroissant_valid,
                schema_valid=schema_valid,
                observed_checksum=observed_checksum,
            )

        updated_registration = self.get_registration(registration_id)
        if updated_registration is None:
            raise ValueError(f"Registration not found: {registration_id}")
        return replace(updated_registration, metadata_path=metadata_path)

    def mark_registration_fetch_failed(
        self,
        registration_id: str,
        error_message: str,
    ) -> StoredRegistration:
        """Persist one fetch/discovery failure on a tracked source."""
        updated_at = datetime.now(UTC)
        error_payload = json.dumps([error_message])

        with self.engine.begin() as connection:
            connection.execute(
                update(registration_sources_table)
                .where(registration_sources_table.c.id == registration_id)
                .values(
                    updated_at=updated_at.isoformat(),
                    last_checked_at=updated_at.isoformat(),
                )
            )
            self._insert_registration_event(
                connection,
                source_id=registration_id,
                registry_entry_id=None,
                event_type="FETCH_FAILED",
                profile_version=None,
                metadata_json=None,
                error_details=error_payload,
                message="Registration fetch/discovery failed.",
                started_at=updated_at.isoformat(),
                finished_at=updated_at.isoformat(),
            )

        updated_registration = self.get_registration(registration_id)
        if updated_registration is None:
            raise ValueError(f"Registration not found: {registration_id}")
        return updated_registration

    def record_revalidation_requested(self, registration_id: str) -> None:
        """Persist an explicit on-demand revalidation request event."""
        updated_at = datetime.now(UTC)
        with self.engine.begin() as connection:
            connection.execute(
                update(registration_sources_table)
                .where(registration_sources_table.c.id == registration_id)
                .values(updated_at=updated_at.isoformat())
            )
            self._insert_registration_event(
                connection,
                source_id=registration_id,
                registry_entry_id=None,
                event_type="REVALIDATED",
                profile_version=None,
                metadata_json=None,
                error_details=None,
                message="On-demand revalidation requested.",
                started_at=updated_at.isoformat(),
                finished_at=updated_at.isoformat(),
            )

    def _initialize_database(self) -> None:
        """Create the schema, apply lightweight migrations, and remove legacy tables."""
        metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            self._ensure_registration_sources_columns(connection)
            connection.execute(text("DROP INDEX IF EXISTS ix_registrations_uniqueness_key"))
            connection.execute(text("DROP TABLE IF EXISTS registration_failures"))
            connection.execute(text("DROP TABLE IF EXISTS registrations"))

    def _build_engine(self) -> Engine:
        """Create the SQLAlchemy engine for the configured SQLite database."""
        return create_engine(f"sqlite+pysqlite:///{self.database_path}")

    def _ensure_registration_sources_columns(self, connection: Engine | object) -> None:
        """Add missing registration source columns for existing SQLite databases."""
        columns = {
            str(row["name"])
            for row in connection.execute(
                text("PRAGMA table_info(registration_sources)")
            ).mappings()
        }
        if "contact_email" not in columns:
            connection.execute(
                text("ALTER TABLE registration_sources ADD COLUMN contact_email VARCHAR")
            )

    def _insert_registration_event(
        self,
        connection: Engine | object,
        *,
        source_id: str,
        registry_entry_id: str | None,
        event_type: str,
        profile_version: str | None,
        metadata_json: str | None,
        error_details: str | None,
        message: str | None,
        started_at: str,
        finished_at: str,
        mlcroissant_valid: bool | None = None,
        schema_valid: bool | None = None,
        observed_checksum: str | None = None,
    ) -> None:
        """Insert one event row into the registration event history."""
        connection.execute(
            insert(registration_events_table).values(
                id=str(uuid4()),
                source_id=source_id,
                registry_entry_id=registry_entry_id,
                event_type=event_type,
                observed_checksum=observed_checksum,
                mlcroissant_valid=mlcroissant_valid,
                schema_valid=schema_valid,
                profile_version=profile_version,
                metadata_json=metadata_json,
                error_details=error_details,
                message=message,
                started_at=started_at,
                finished_at=finished_at,
                notification_sent=False,
            )
        )

    def _source_row(
        self,
        connection: Engine | object,
        registration_id: str,
    ) -> RowMapping | None:
        """Load one source row when it exists."""
        return connection.execute(
            select(registration_sources_table).where(
                registration_sources_table.c.id == registration_id
            )
        ).mappings().first()

    def _current_registry_entry(
        self,
        connection: Engine | object,
        source_id: str,
    ) -> RowMapping | None:
        """Load the current canonical registry entry for one source when it exists."""
        source_row = self._source_row(connection, source_id)
        if source_row is None or source_row["current_registry_entry_id"] is None:
            return None
        return connection.execute(
            select(registry_entries_table).where(
                registry_entries_table.c.id == source_row["current_registry_entry_id"]
            )
        ).mappings().first()

    def _latest_event_for_source(
        self,
        connection: Engine | object,
        source_id: str,
    ) -> RowMapping | None:
        """Load the latest event row for one source when it exists."""
        return connection.execute(
            select(registration_events_table)
            .where(registration_events_table.c.source_id == source_id)
            .order_by(
                registration_events_table.c.finished_at.desc(),
                registration_events_table.c.started_at.desc(),
                registration_events_table.c.id.desc(),
            )
        ).mappings().first()

    def _registry_entry_by_uniqueness_key(
        self,
        connection: Engine | object,
        uniqueness_key: str,
    ) -> RowMapping | None:
        """Load one canonical registry entry by uniqueness key when it exists."""
        return connection.execute(
            select(registry_entries_table).where(
                registry_entries_table.c.uniqueness_key == uniqueness_key
            )
        ).mappings().first()

    def _event_row_to_event(self, event_row: RowMapping) -> RegistrationEvent:
        """Convert one event row into the public core event model."""
        error_details = (
            self._parse_error_details(str(event_row["error_details"]))
            if event_row["error_details"]
            else None
        )
        return RegistrationEvent(
            event_id=str(event_row["id"]),
            source_id=str(event_row["source_id"]),
            registry_entry_id=(
                str(event_row["registry_entry_id"])
                if event_row["registry_entry_id"] is not None
                else None
            ),
            event_type=str(event_row["event_type"]),
            message=(
                str(event_row["message"]) if event_row["message"] is not None else None
            ),
            profile_version=(
                str(event_row["profile_version"])
                if event_row["profile_version"] is not None
                else None
            ),
            error_details=error_details,
            observed_checksum=(
                str(event_row["observed_checksum"])
                if event_row["observed_checksum"] is not None
                else None
            ),
            mlcroissant_valid=event_row["mlcroissant_valid"],
            schema_valid=event_row["schema_valid"],
            started_at=datetime.fromisoformat(str(event_row["started_at"])),
            finished_at=datetime.fromisoformat(str(event_row["finished_at"])),
        )

    def _registry_entry_row_to_entry(self, entry_row: RowMapping) -> RegistryEntry:
        """Convert one registry entry row into the public core entry model."""
        return RegistryEntry(
            entry_id=str(entry_row["id"]),
            source_id=str(entry_row["source_id"]),
            adapter_name=str(entry_row["adapter_name"]),
            adapter_version=str(entry_row["adapter_version"]),
            profile_version=(
                str(entry_row["profile_version"])
                if entry_row["profile_version"] is not None
                else None
            ),
            uniqueness_key=str(entry_row["uniqueness_key"]),
            metadata_checksum=(
                str(entry_row["metadata_checksum"])
                if entry_row["metadata_checksum"] is not None
                else None
            ),
            created_at=datetime.fromisoformat(str(entry_row["created_at"])),
            updated_at=datetime.fromisoformat(str(entry_row["updated_at"])),
            metadata=self._parse_json(entry_row["metadata_json"]),
            is_active=bool(entry_row["is_active"]),
        )

    def _refresh_row_to_record(self, refresh_row: RowMapping) -> BatchRefreshRecord:
        """Convert one refresh row into the public core refresh model."""
        return BatchRefreshRecord(
            refresh_id=str(refresh_row["id"]),
            started_at=datetime.fromisoformat(str(refresh_row["started_at"])),
            finished_at=datetime.fromisoformat(str(refresh_row["finished_at"])),
            active_sources=int(refresh_row["active_sources"]),
            processed=int(refresh_row["processed"]),
            valid_created=int(refresh_row["valid_created"]),
            unchanged=int(refresh_row["unchanged"]),
            invalid=int(refresh_row["invalid"]),
            duplicate=int(refresh_row["duplicate"]),
            rejected_same_version_changed=int(
                refresh_row["rejected_same_version_changed"]
            ),
            fetch_failed=int(refresh_row["fetch_failed"]),
        )

    def _source_to_registration(
        self,
        source_row: RowMapping,
        current_entry: RowMapping | None,
        latest_event: RowMapping | None,
    ) -> StoredRegistration:
        """Convert three-table state into the public registration model."""
        latest_event_type = (
            str(latest_event["event_type"]) if latest_event is not None else "SUBMITTED"
        )
        current_metadata = self._parse_json(current_entry["metadata_json"]) if current_entry else None
        latest_event_metadata = (
            self._parse_json(latest_event["metadata_json"])
            if latest_event is not None and latest_event["metadata_json"]
            else None
        )
        metadata = self._select_registration_metadata(
            latest_event_type=latest_event_type,
            current_metadata=current_metadata,
            latest_event_metadata=latest_event_metadata,
        )
        adapter_id = self._resolve_registration_adapter_id(
            metadata=metadata,
            submitted_adapter_name=str(source_row["submitted_adapter_name"]),
        )
        uniqueness_key = (
            str(current_entry["uniqueness_key"])
            if current_entry is not None and current_entry["uniqueness_key"] is not None
            else self._best_effort_uniqueness_key(metadata, str(source_row["submitted_adapter_name"]))
        )
        validation_errors = (
            self._parse_error_details(str(latest_event["error_details"]))
            if latest_event is not None and latest_event["error_details"]
            else None
        )

        return StoredRegistration(
            registration_id=str(source_row["id"]),
            adapter_name=str(source_row["submitted_adapter_name"]),
            adapter_id=adapter_id,
            repository_location=str(source_row["repository_location"]),
            repository_kind=str(source_row["source_kind"]),
            status=self._derive_status(latest_event_type, current_entry),
            created_at=datetime.fromisoformat(str(source_row["created_at"])),
            contact_email=source_row.get("contact_email"),
            metadata_path=self._resolve_metadata_path(source_row),
            metadata=metadata,
            profile_version=self._select_profile_version(current_entry, latest_event),
            updated_at=datetime.fromisoformat(str(source_row["updated_at"])),
            last_checked_at=(
                datetime.fromisoformat(str(source_row["last_checked_at"]))
                if source_row["last_checked_at"] is not None
                else None
            ),
            current_registry_entry_id=(
                str(source_row["current_registry_entry_id"])
                if source_row["current_registry_entry_id"] is not None
                else None
            ),
            uniqueness_key=uniqueness_key,
            validation_errors=validation_errors,
        )

    def _resolve_registration_adapter_id(
        self,
        *,
        metadata: dict[str, object] | None,
        submitted_adapter_name: str,
    ) -> str:
        """Resolve the public adapter id from metadata first, then submitted name."""
        if metadata is not None:
            metadata_adapter_id = str(metadata.get("@id", "")).strip()
            if metadata_adapter_id:
                return slugify_identifier(metadata_adapter_id)
            metadata_name = str(metadata.get("name", "")).strip()
            if metadata_name:
                return slugify_identifier(metadata_name)
        return slugify_identifier(submitted_adapter_name)

    def _best_effort_uniqueness_key(
        self,
        metadata_payload: dict[str, object] | None,
        submitted_adapter_name: str,
    ) -> str | None:
        """Build a uniqueness key from available metadata when possible."""
        if metadata_payload is None:
            return None
        version = str(metadata_payload.get("version", "")).strip()
        if not version:
            return None
        adapter_id = self._resolve_registration_adapter_id(
            metadata=metadata_payload,
            submitted_adapter_name=submitted_adapter_name,
        )
        if not adapter_id:
            return None
        return f"{adapter_id}::{version}"

    def _derive_status(
        self,
        latest_event_type: str,
        current_entry: RowMapping | None,
    ) -> RegistrationStatus:
        """Map the latest event plus canonical state into a public status."""
        if latest_event_type.startswith("INVALID_"):
            return RegistrationStatus.INVALID
        if current_entry is not None:
            return RegistrationStatus.VALID
        return RegistrationStatus.SUBMITTED

    def _select_profile_version(
        self,
        current_entry: RowMapping | None,
        latest_event: RowMapping | None,
    ) -> str | None:
        """Select the most relevant profile version for one registration."""
        if latest_event is not None and latest_event["profile_version"] is not None:
            return str(latest_event["profile_version"])
        if current_entry is not None and current_entry["profile_version"] is not None:
            return str(current_entry["profile_version"])
        return None

    def _select_registration_metadata(
        self,
        *,
        latest_event_type: str,
        current_metadata: dict[str, object] | None,
        latest_event_metadata: dict[str, object] | None,
    ) -> dict[str, object] | None:
        """Choose which metadata payload best represents the registration state."""
        if latest_event_type.startswith("INVALID_"):
            return latest_event_metadata
        if latest_event_type in {"DUPLICATE", "REJECTED_SAME_VERSION_CHANGED", "FETCH_FAILED"}:
            return latest_event_metadata
        if current_metadata is not None:
            return current_metadata
        return latest_event_metadata

    def _resolve_metadata_path(self, source_row: RowMapping) -> str | None:
        """Best-effort resolution of the current local metadata path."""
        if str(source_row["source_kind"]) != "local":
            return None
        try:
            metadata_path, _ = fetch_local_metadata(str(source_row["repository_location"]))
        except Exception:  # noqa: BLE001
            return None
        return str(metadata_path)

    def _parse_json(self, payload: object) -> dict[str, object] | None:
        """Parse one stored JSON payload when it exists."""
        if payload in (None, ""):
            return None
        return json.loads(str(payload))

    def _parse_error_details(self, payload: str) -> list[str]:
        """Parse stored error details into a string list."""
        parsed = json.loads(payload)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
        return [str(parsed)]
