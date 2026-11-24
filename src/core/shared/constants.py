"""Constants shared across Croissant document generation and validation."""

from __future__ import annotations

METADATA_FILENAME = "croissant.jsonld"
JSONLD_TYPE_KEY = "@type"
DCT_CONFORMS_TO_KEY = "dct:conformsTo"

# Canonical JSON-LD identifiers, not network transport endpoints. See the
# namespaces and JSON-LD context in the Croissant specification:
# https://docs.mlcommons.org/croissant/docs/croissant-spec.html
CROISSANT_NAMESPACE_IRI = (
    "http://mlcommons.org/croissant/"  # NOSONAR(S5332) canonical vocabulary IRI.
)
CROISSANT_RAI_NAMESPACE_IRI = (
    "http://mlcommons.org/croissant/RAI/"  # NOSONAR(S5332) canonical vocabulary IRI.
)
CROISSANT_CONFORMS_TO_URL = (
    "http://mlcommons.org/croissant/1.0"  # NOSONAR(S5332) required profile identifier.
)

STANDARD_CONTEXT = {
    "@language": "en",
    "@vocab": "https://schema.org/",
    "sc": "https://schema.org/",
    "cr": CROISSANT_NAMESPACE_IRI,
    "rai": CROISSANT_RAI_NAMESPACE_IRI,
    "dct": "http://purl.org/dc/terms/",
    "bsc": "https://bioschemas.org/profiles/Dataset/1.0-RELEASE/",
    "citeAs": "cr:citeAs",
    "column": "cr:column",
    "conformsTo": DCT_CONFORMS_TO_KEY,
    "data": {"@id": "cr:data", JSONLD_TYPE_KEY: "@json"},
    "dataType": {"@id": "cr:dataType", JSONLD_TYPE_KEY: "@vocab"},
    "examples": {"@id": "cr:examples", JSONLD_TYPE_KEY: "@json"},
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

MANDATORY_FIELDS = (
    "name",
    "description",
    "version",
    "license",
    "url",
)

DEFAULT_PROFILE_URL = "https://bioschemas.org/profiles/ComputationalTool/1.0-RELEASE/"
DEFAULT_PROGRAMMING_LANGUAGE = "Python"
DEFAULT_TARGET_PRODUCT = "BioCypher"

__all__ = [
    "CROISSANT_CONFORMS_TO_URL",
    "CROISSANT_NAMESPACE_IRI",
    "CROISSANT_RAI_NAMESPACE_IRI",
    "DCT_CONFORMS_TO_KEY",
    "DEFAULT_PROFILE_URL",
    "DEFAULT_PROGRAMMING_LANGUAGE",
    "DEFAULT_TARGET_PRODUCT",
    "JSONLD_TYPE_KEY",
    "MANDATORY_FIELDS",
    "METADATA_FILENAME",
    "STANDARD_CONTEXT",
]
