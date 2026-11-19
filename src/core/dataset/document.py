"""Builders for standalone dataset Croissant documents."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.core.shared.constants import (
    CROISSANT_1_0_CONTEXT,
    CROISSANT_CONFORMS_TO_URL,
)

JSONLD_TYPE_KEY = "@type"

DATASET_CONTEXT: dict[str, Any] = CROISSANT_1_0_CONTEXT


def build_creator(
    name: str,
    url: str = "",
    email: str = "",
    affiliation: str = "",
    identifier: str = "",
    creator_type: str = "Person",
) -> dict[str, Any]:
    """Build a creator node for dataset metadata."""
    normalized_type = (
        "Organization"
        if str(creator_type).strip().lower() == "organization"
        else "Person"
    )
    creator: dict[str, Any] = {
        JSONLD_TYPE_KEY: f"sc:{normalized_type}",
        "name": name,
    }
    if affiliation:
        creator["affiliation"] = affiliation
    if email:
        creator["email"] = email
    if url:
        creator["url"] = url
    if identifier:
        creator["identifier"] = identifier
    return creator


def build_distribution_file(
    content_url: str,
    encoding_format: str | list[str],
    name: str,
    file_id: str,
    content_size: str = "",
    sha256: str = "",
) -> dict[str, Any]:
    """Build a Croissant ``FileObject`` entry for a dataset distribution."""
    file_object = {
        JSONLD_TYPE_KEY: "cr:FileObject",
        "@id": file_id,
        "name": name,
    }
    if content_size:
        file_object["contentSize"] = content_size
    file_object["contentUrl"] = content_url
    file_object["encodingFormat"] = encoding_format
    if sha256:
        file_object["sha256"] = sha256
    return file_object


def build_field(
    *,
    name: str,
    data_type: str,
    description_suffix: str = "",
    record_set_id: str,
    file_object_id: str,
) -> dict[str, Any]:
    """Build a Croissant field entry sourced from a file column."""
    description = f"Column '{name}'"
    if description_suffix:
        description = f"{description} from {description_suffix}"
    return {
        JSONLD_TYPE_KEY: "cr:Field",
        "@id": f"{record_set_id}/{name}",
        "name": name,
        "description": description,
        "dataType": data_type,
        "source": {
            "@id": f"{record_set_id}/{name}/source",
            "fileObject": {"@id": file_object_id},
            "extract": {"column": name},
        },
    }


def build_record_set(
    *,
    name: str,
    record_set_id: str,
    fields: list[dict[str, Any]],
    description: str = "",
) -> dict[str, Any]:
    """Build a Croissant record set node."""
    record_set = {
        JSONLD_TYPE_KEY: "cr:RecordSet",
        "@id": record_set_id,
        "name": name,
    }
    if description:
        record_set["description"] = description
    record_set["field"] = fields
    return record_set


def build_dataset_document(
    *,
    name: str,
    description: str,
    version: str,
    license_value: str,
    url: str,
    date_published: str,
    citation: str,
    creators: list[dict[str, Any]],
    distributions: list[dict[str, Any]],
    record_sets: list[dict[str, Any]],
) -> dict[str, Any]:
    """Assemble a full standalone dataset Croissant document."""
    document: dict[str, Any] = {
        "@context": deepcopy(DATASET_CONTEXT),
        JSONLD_TYPE_KEY: "sc:Dataset",
        "name": name,
        "description": description,
        "conformsTo": CROISSANT_CONFORMS_TO_URL,
    }
    if citation:
        document["citeAs"] = citation
    if creators:
        document["creator"] = creators[0] if len(creators) == 1 else creators
    if date_published:
        document["datePublished"] = date_published
    document["license"] = license_value
    document["url"] = url
    document["version"] = version
    document["distribution"] = distributions
    document["recordSet"] = record_sets
    return document
