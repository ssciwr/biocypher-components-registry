"""Builders for adapter Croissant documents and embedded dataset fragments."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.core.shared.constants import (
    CROISSANT_CONFORMS_TO_URL,
    DCT_CONFORMS_TO_KEY,
    STANDARD_CONTEXT,
)
from src.core.shared.ids import slugify_identifier

JSONLD_TYPE_KEY = "@type"

ADAPTER_CONTEXT: dict[str, Any] = STANDARD_CONTEXT


def build_adapter_creator(
    name: str,
    affiliation: str = "",
    identifier: str = "",
    creator_type: str = "Person",
    email: str = "",
    url: str = "",
) -> dict[str, Any]:
    """Build a creator node for adapter metadata."""
    normalized_type = (
        "Organization"
        if str(creator_type).strip().lower() == "organization"
        else "Person"
    )
    creator: dict[str, Any] = {JSONLD_TYPE_KEY: normalized_type, "name": name}
    if affiliation:
        creator["affiliation"] = affiliation
    if email:
        creator["email"] = email
    if url:
        creator["url"] = url
    if identifier:
        creator["identifier"] = identifier
    return creator


def build_adapter_document(
    *,
    name: str,
    description: str,
    version: str,
    license_value: str,
    code_repository: str,
    creators: list[dict[str, Any]],
    keywords: list[str],
    datasets: list[dict[str, Any]],
    adapter_id: str | None = None,
) -> dict[str, Any]:
    """Assemble a full adapter metadata document."""
    document: dict[str, Any] = {
        "@context": deepcopy(ADAPTER_CONTEXT),
        JSONLD_TYPE_KEY: "SoftwareSourceCode",
        DCT_CONFORMS_TO_KEY: "https://bioschemas.org/profiles/ComputationalTool/1.0-RELEASE/",
        "@id": adapter_id or slugify_identifier(name),
        "name": name,
        "description": description,
        "version": version,
        "license": license_value,
        "codeRepository": code_repository,
        "creator": creators,
        "keywords": keywords,
        "hasPart": datasets,
    }
    return document


def build_dataset_distribution_file(
    *,
    content_url: str,
    encoding_format: str,
    name: str,
    file_id: str,
    md5: str = "",
    sha256: str = "",
) -> dict[str, Any]:
    """Build a dataset distribution file entry for embedded metadata."""
    document: dict[str, Any] = {
        JSONLD_TYPE_KEY: "cr:FileObject",
        "@id": file_id,
        "name": name,
        "contentUrl": content_url,
        "encodingFormat": encoding_format,
    }
    if md5:
        document["md5"] = md5
    if sha256:
        document["sha256"] = sha256
    return document


def build_dataset_field(
    *,
    name: str,
    description: str,
    data_type: str,
    examples: list[Any],
    record_set_id: str,
    file_object_id: str,
) -> dict[str, Any]:
    """Build a field node for an embedded dataset record set."""
    field: dict[str, Any] = {
        JSONLD_TYPE_KEY: "cr:Field",
        "@id": f"{record_set_id}/{name}",
        "name": name,
        "description": description,
        "dataType": data_type,
        "source": {
            "fileObject": {"@id": file_object_id},
            "extract": {"column": name},
        },
    }
    if examples:
        field["examples"] = examples
    return field


def build_embedded_dataset_document(
    *,
    name: str,
    description: str,
    version: str,
    license_value: str,
    url: str,
    date_published: str = "",
    citation: str = "",
    creators: list[dict[str, Any]] | None = None,
    distributions: list[dict[str, Any]] | None = None,
    record_sets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a dataset fragment suitable for embedding under ``hasPart``."""
    document: dict[str, Any] = {
        JSONLD_TYPE_KEY: "sc:Dataset",
        DCT_CONFORMS_TO_KEY: CROISSANT_CONFORMS_TO_URL,
        "name": name,
        "description": description,
        "version": version,
        "license": license_value,
        "url": url,
    }
    if date_published:
        document["datePublished"] = date_published
    if citation:
        document["citeAs"] = citation
    if creators:
        document["creator"] = creators
    if distributions:
        document["distribution"] = distributions
    if record_sets:
        document["recordSet"] = record_sets
    return document


def build_embedded_record_set(
    *,
    name: str,
    record_set_id: str,
    fields: list[dict[str, Any]],
    description: str = "",
) -> dict[str, Any]:
    """Build a record set node for an embedded dataset fragment."""
    record_set: dict[str, Any] = {
        JSONLD_TYPE_KEY: "cr:RecordSet",
        "@id": record_set_id,
        "name": name,
        "field": fields,
    }
    if description:
        record_set["description"] = description
    return record_set
