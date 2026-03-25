"""
Shared constants for the core package.
"""

METADATA_FILENAME = "croissant.jsonld"

# JSON-LD context shared by generated Croissant documents.
STANDARD_CONTEXT = {
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

# Mandatory fields required by the guided metadata flow (US-02).
MANDATORY_FIELDS = (
    "name",
    "description",
    "version",
    "license",
    "url",
)

# Default Croissant/BioCypher profile constants.
DEFAULT_PROFILE_URL = (
    "https://bioschemas.org/profiles/ComputationalTool/1.0-RELEASE/"
)
CROISSANT_CONFORMS_TO_URL = "http://mlcommons.org/croissant/1.0"
DEFAULT_PROGRAMMING_LANGUAGE = "Python"
DEFAULT_TARGET_PRODUCT = "BioCypher"
