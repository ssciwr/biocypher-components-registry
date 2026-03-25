"""Builders for standalone dataset Croissant documents."""

from __future__ import annotations

from typing import Any


DATASET_CONTEXT: dict[str, Any] = {
    "@language": "en",
    "@vocab": "https://schema.org/",
    "citeAs": "cr:citeAs",
    "column": "cr:column",
    "conformsTo": "dct:conformsTo",
    "cr": "http://mlcommons.org/croissant/",
    "rai": "http://mlcommons.org/croissant/RAI/",
    "data": {"@id": "cr:data", "@type": "@json"},
    "dataType": {"@id": "cr:dataType", "@type": "@vocab"},
    "dct": "http://purl.org/dc/terms/",
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
    "sc": "https://schema.org/",
    "separator": "cr:separator",
    "source": "cr:source",
    "subField": "cr:subField",
    "transform": "cr:transform",
}


def build_creator(
    name: str,
    url: str = "",
    email: str = "",
    affiliation: str = "",
    creator_type: str = "Person",
) -> dict[str, Any]:
    """Build a creator node for dataset metadata."""
    normalized_type = "Organization" if str(creator_type).strip().lower() == "organization" else "Person"
    creator: dict[str, Any] = {"@type": f"sc:{normalized_type}", "name": name}
    if affiliation:
        creator["affiliation"] = affiliation
    if email:
        creator["email"] = email
    if url:
        creator["url"] = url
    return creator


def build_distribution_file(
    content_url: str,
    encoding_format: str,
    name: str,
    file_id: str,
    content_size: str = "",
    sha256: str = "",
) -> dict[str, Any]:
    """Build a Croissant ``FileObject`` entry for a dataset distribution."""
    file_object = {
        "@type": "cr:FileObject",
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
        "@type": "cr:Field",
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
        "@type": "cr:RecordSet",
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
        "@context": DATASET_CONTEXT,
        "@type": "sc:Dataset",
        "name": name,
        "description": description,
        "conformsTo": "http://mlcommons.org/croissant/1.0",
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
