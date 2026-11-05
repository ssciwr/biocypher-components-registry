"""Accepted and historical source fixtures without the removed staging API."""

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import insert

from src.core.adapter.service import create_registration_request
from src.persistence.tables import registration_sources_table


def accepted_source(
    store, repository_location, *, metadata=None, owner="123", **fields
):
    """Seed persistence/catalog tests directly through atomic acceptance."""
    metadata = metadata or {
        "@id": "example-adapter",
        "name": "Example Adapter",
        "version": "1.0.0",
    }
    request = create_registration_request(
        repository_location, submitted_by_github_user_id=owner, **fields
    )
    checksum = hashlib.sha256(
        json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return store.accept_candidate(
        request, metadata, "v1", f"{metadata['@id']}::{metadata['version']}", checksum
    )


def historical_source(store, repository_location, *, owner="123", **fields):
    """Represent a pre-migration unpublished source without producing new stages."""
    request = create_registration_request(
        repository_location, submitted_by_github_user_id=owner, **fields
    )
    identifier = str(uuid4())
    now = datetime.now(UTC).isoformat()
    with store.engine.begin() as connection:
        connection.execute(
            insert(registration_sources_table).values(
                id=identifier,
                submitted_adapter_name=request.adapter_name,
                description=request.description,
                repository_location=request.repository_location,
                source_kind=request.repository_kind,
                license_value=request.license_value,
                doi=request.doi,
                cff_url=request.cff_url,
                submitted_by_github_user_id=owner,
                is_active=True,
                created_at=now,
                updated_at=now,
                current_registry_entry_id=None,
            )
        )
    return store.get_registration(identifier)
