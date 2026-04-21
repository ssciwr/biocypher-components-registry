from __future__ import annotations

from src.persistence.tables import (
    registration_events_table,
    registration_sources_table,
    registry_entries_table,
    registry_refreshes_table,
)

def test_registration_sources_table_has_expected_columns() -> None:
    """Expose the expected source columns through SQLAlchemy metadata."""
    assert registration_sources_table.name == "registration_sources"
    assert set(registration_sources_table.columns.keys()) == {
        "id",
        "submitted_adapter_name",
        "repository_location",
        "source_kind",
        "contact_email",
        "is_active",
        "created_at",
        "updated_at",
        "last_checked_at",
        "last_seen_at",
        "current_registry_entry_id",
    }


def test_registry_entries_table_has_expected_columns() -> None:
    """Expose the expected canonical entry columns through SQLAlchemy metadata."""
    assert registry_entries_table.name == "registry_entries"
    assert set(registry_entries_table.columns.keys()) == {
        "id",
        "source_id",
        "adapter_name",
        "adapter_version",
        "profile_version",
        "uniqueness_key",
        "metadata_checksum",
        "metadata_json",
        "created_at",
        "updated_at",
        "is_active",
    }


def test_registration_events_table_has_expected_columns() -> None:
    """Expose the expected event-history columns through SQLAlchemy metadata."""
    assert registration_events_table.name == "registration_events"
    assert set(registration_events_table.columns.keys()) == {
        "id",
        "source_id",
        "registry_entry_id",
        "event_type",
        "observed_checksum",
        "mlcroissant_valid",
        "schema_valid",
        "profile_version",
        "metadata_json",
        "error_details",
        "message",
        "started_at",
        "finished_at",
        "notification_sent",
    }


def test_registry_refreshes_table_has_expected_columns() -> None:
    """Expose the expected batch refresh columns through SQLAlchemy metadata."""
    assert registry_refreshes_table.name == "registry_refreshes"
    assert set(registry_refreshes_table.columns.keys()) == {
        "id",
        "started_at",
        "finished_at",
        "active_sources",
        "processed",
        "valid_created",
        "unchanged",
        "invalid",
        "duplicate",
        "rejected_same_version_changed",
        "fetch_failed",
    }
