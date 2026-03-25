"""Croissant document builder.

Assembles a well-formed ``croissant.jsonld`` dict from structured Python
inputs. The builder is intentionally decoupled from I/O — it only
constructs dicts. Callers (CLI wizard, tests) serialize to JSON.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


_STANDARD_CONTEXT: Dict[str, Any] = {
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


def build_adapter(
    name: str,
    description: str,
    version: str,
    license_url: str,
    code_repository: str,
    creators: List[Dict[str, Any]],
    keywords: List[str],
    datasets: List[Dict[str, Any]],
    adapter_id: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Assemble a complete ``croissant.jsonld`` document dict."""
    doc: Dict[str, Any] = {
        "@context": _STANDARD_CONTEXT,
        "@type": "SoftwareSourceCode",
        "dct:conformsTo": (
            "https://bioschemas.org/profiles/ComputationalTool/1.0-RELEASE/"
        ),
        "@id": adapter_id if adapter_id else _slugify(name),
        "name": name,
        "description": description,
        "version": version,
        "license": license_url,
        "codeRepository": code_repository,
        "programmingLanguage": "Python",
        "targetProduct": "BioCypher",
        "creator": creators,
        "keywords": keywords,
        "hasPart": datasets,
    }

    if extra:
        doc.update(extra)

    return doc


def build_creator(
    name: str,
    affiliation: str = "",
    orcid: str = "",
) -> Dict[str, Any]:
    """Build a creator dict for embedding in an adapter or dataset."""
    creator: Dict[str, Any] = {"@type": "Person", "name": name}
    if affiliation:
        creator["affiliation"] = affiliation
    if orcid:
        creator["identifier"] = orcid
    return creator


def build_dataset(
    name: str,
    description: str,
    version: str,
    license_url: str,
    url: str,
    date_published: str = "",
    cite_as: str = "",
    creators: Optional[List[Dict[str, Any]]] = None,
    distribution: Optional[List[Dict[str, Any]]] = None,
    record_set: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Build a single ``hasPart`` dataset entry."""
    ds: Dict[str, Any] = {
        "@type": "sc:Dataset",
        "dct:conformsTo": "http://mlcommons.org/croissant/1.0",
        "name": name,
        "description": description,
        "version": version,
        "license": license_url,
        "url": url,
    }
    if date_published:
        ds["datePublished"] = date_published
    if cite_as:
        ds["citeAs"] = cite_as
    if creators:
        ds["creator"] = creators
    if distribution:
        ds["distribution"] = distribution
    if record_set:
        ds["recordSet"] = record_set
    return ds


def build_distribution_file(
    content_url: str,
    encoding_format: str,
    name: str = "",
    file_id: Optional[str] = None,
    md5: str = "",
    sha256: str = "",
) -> Dict[str, Any]:
    """Build a ``cr:FileObject`` distribution entry."""
    resolved_name = name or content_url.rstrip("/").split("/")[-1]
    resolved_id = file_id if file_id else _slugify(resolved_name)
    file_object: Dict[str, Any] = {
        "@type": "cr:FileObject",
        "@id": resolved_id,
        "name": resolved_name,
        "contentUrl": content_url,
        "encodingFormat": encoding_format,
    }
    if md5:
        file_object["md5"] = md5
    if sha256:
        file_object["sha256"] = sha256
    return file_object


def build_field(
    name: str,
    description: str,
    data_type: str,
    examples: List[Any],
    record_set_id: str,
    file_object_id: str,
) -> Dict[str, Any]:
    """Build a ``cr:Field`` entry for a RecordSet."""
    return {
        "@type": "cr:Field",
        "@id": f"{record_set_id}/{name}",
        "name": name,
        "description": description,
        "dataType": data_type,
        "examples": examples,
        "source": {
            "fileObject": {"@id": file_object_id},
            "extract": {"column": name},
        },
    }


def build_record_set(
    name: str,
    fields: List[Dict[str, Any]],
    description: str = "",
    record_set_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a ``cr:RecordSet`` entry."""
    rs: Dict[str, Any] = {
        "@type": "cr:RecordSet",
        "@id": record_set_id if record_set_id else _slugify(name),
        "name": name,
        "field": fields,
    }
    if description:
        rs["description"] = description
    return rs


def _slugify(text: str) -> str:
    """Derive a URL-safe slug from an adapter name."""
    return text.lower().replace(" ", "-").replace("_", "-")
