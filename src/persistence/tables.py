"""Shared SQLAlchemy table definitions for registration persistence."""

from __future__ import annotations

from sqlalchemy import Boolean, Column, Integer, MetaData, String, Table


metadata = MetaData()

registration_sources_table = Table(
    "registration_sources",
    metadata,
    Column("id", String, primary_key=True),
    Column("submitted_adapter_name", String, nullable=False),
    Column("repository_location", String, nullable=False),
    Column("source_kind", String, nullable=False),
    Column("contact_email", String, nullable=True),
    Column("is_active", Boolean, nullable=False),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
    Column("last_checked_at", String, nullable=True),
    Column("last_seen_at", String, nullable=True),
    Column("current_registry_entry_id", String, nullable=True),
)

registry_entries_table = Table(
    "registry_entries",
    metadata,
    Column("id", String, primary_key=True),
    Column("source_id", String, nullable=False),
    Column("adapter_name", String, nullable=False),
    Column("adapter_version", String, nullable=False),
    Column("profile_version", String, nullable=True),
    Column("uniqueness_key", String, nullable=False, unique=True),
    Column("metadata_checksum", String, nullable=True),
    Column("metadata_json", String, nullable=False),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
    Column("is_active", Boolean, nullable=False),
)

registration_events_table = Table(
    "registration_events",
    metadata,
    Column("id", String, primary_key=True),
    Column("source_id", String, nullable=False),
    Column("registry_entry_id", String, nullable=True),
    Column("event_type", String, nullable=False),
    Column("observed_checksum", String, nullable=True),
    Column("mlcroissant_valid", Boolean, nullable=True),
    Column("schema_valid", Boolean, nullable=True),
    Column("profile_version", String, nullable=True),
    Column("metadata_json", String, nullable=True),
    Column("error_details", String, nullable=True),
    Column("message", String, nullable=True),
    Column("started_at", String, nullable=False),
    Column("finished_at", String, nullable=False),
    Column("notification_sent", Boolean, nullable=False),
)

registry_refreshes_table = Table(
    "registry_refreshes",
    metadata,
    Column("id", String, primary_key=True),
    Column("started_at", String, nullable=False),
    Column("finished_at", String, nullable=False),
    Column("active_sources", Integer, nullable=False),
    Column("processed", Integer, nullable=False),
    Column("valid_created", Integer, nullable=False),
    Column("unchanged", Integer, nullable=False),
    Column("invalid", Integer, nullable=False),
    Column("duplicate", Integer, nullable=False),
    Column("rejected_same_version_changed", Integer, nullable=False),
    Column("fetch_failed", Integer, nullable=False),
)
