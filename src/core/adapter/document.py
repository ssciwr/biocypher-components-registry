"""Builders for adapter Croissant documents and embedded dataset fragments."""

from __future__ import annotations

from typing import Any

from src.core.shared.ids import slugify_identifier


ADAPTER_CONTEXT: dict[str, Any] = {
    "@language": "en",
    "@vocab": "https://schema.org/",
    "sc": "https://schema.org/",
    "cr": "http://mlcommons.org/croissant/",
    "rai": "http://mlcommons.org/croissant/RAI/",
    "dct": "http://purl.org/dc/terms/",
    "bsc": "https://bioschemas.org/profiles/Dataset/1.0-RELEASE/",
    "citeAs": "cr:citeAs",
    "column": "cr:column",
    "conformsTo": "dct:conformsTo",
    "data": {"@id": "cr:data", "@type": "@json"},
    "dataType": {"@id": "cr:dataType", "@type": "@vocab"},
    "examples": {"@id": "cr:examples", "@type": "@json"},
    "extract": "cr:extract",
    "field": "cr:field",
    "fileProperty": "cr:fileProperty",
    "fileObject": "cr:fileObject",
    "fileSet": "cr:fileSet",
    "format": "cr:format",
    "includes": "cr:includes",
    "isLiveDataset": "cr:isLiveDataset",
    "jsonPath": "cr:jsonPath",
    "key": "cr:key",
    "md5": "cr:md5",
    "parentField": "cr:parentField",
    "path": "cr:path",
    "recordSet": "cr:recordSet",
    "references": "cr:references",
    "regex": "cr:regex",
    "repeated": "cr:repeated",
    "replace": "cr:replace",
    "samplingRate": "cr:samplingRate",
    "separator": "cr:separator",
    "source": "cr:source",
    "subField": "cr:subField",
    "transform": "cr:transform",
}


def build_adapter_creator(
    name: str,
    affiliation: str = "",
    identifier: str = "",
    creator_type: str = "Person",
) -> dict[str, Any]:
    """Build a creator node for adapter metadata."""
    normalized_type = (
        "Organization"
        if str(creator_type).strip().lower() == "organization"
        else "Person"
    )
    creator: dict[str, Any] = {"@type": normalized_type, "name": name}
    if affiliation:
        creator["affiliation"] = affiliation
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
    programming_language: str = "Python",
    target_product: str = "BioCypher",
) -> dict[str, Any]:
    """Assemble a full adapter metadata document."""
    document: dict[str, Any] = {
        "@context": ADAPTER_CONTEXT,
        "@type": "SoftwareSourceCode",
        "dct:conformsTo": "https://bioschemas.org/profiles/ComputationalTool/1.0-RELEASE/",
        "@id": adapter_id or slugify_identifier(name),
        "name": name,
        "description": description,
        "version": version,
        "license": license_value,
        "codeRepository": code_repository,
        "programmingLanguage": programming_language,
        "targetProduct": target_product,
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
        "@type": "cr:FileObject",
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
        "@type": "cr:Field",
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
        "@type": "sc:Dataset",
        "dct:conformsTo": "http://mlcommons.org/croissant/1.0",
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
        "@type": "cr:RecordSet",
        "@id": record_set_id,
        "name": name,
        "field": fields,
    }
    if description:
        record_set["description"] = description
    return record_set
