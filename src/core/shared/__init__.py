"""Convenience exports for shared constants, helpers, and error types."""

from __future__ import annotations

from src.core.shared.constants import (
    CROISSANT_CONFORMS_TO_URL,
    DEFAULT_PROFILE_URL,
    DEFAULT_PROGRAMMING_LANGUAGE,
    DEFAULT_TARGET_PRODUCT,
    MANDATORY_FIELDS,
    METADATA_FILENAME,
    STANDARD_CONTEXT,
)
from src.core.shared.creators import (
    CreatorSpec,
    parse_adapter_creator_string,
    parse_dataset_creator_string,
)
from src.core.shared.errors import (
    AmbiguousMetadataFileError,
    GenerationValidationError,
    GeneratorError,
    InputDiscoveryError,
    InvalidMetadataJSONError,
    InvalidRepoURLError,
    MetadataDiscoveryError,
    MetadataFileNotFoundError,
    MetadataNotFoundError,
    RemoteResourceNotFoundError,
    UnsupportedFormatError,
    UnsupportedGeneratorError,
)
from src.core.shared.ids import slugify_identifier
from src.core.shared.licenses import normalize_license_url
from src.core.shared.files import (
    fetch_local_file,
    fetch_local_metadata,
    fetch_remote_file,
    fetch_remote_metadata,
    parse_json_metadata,
)

__all__ = [
    "CROISSANT_CONFORMS_TO_URL",
    "CreatorSpec",
    "DEFAULT_PROFILE_URL",
    "DEFAULT_PROGRAMMING_LANGUAGE",
    "DEFAULT_TARGET_PRODUCT",
    "AmbiguousMetadataFileError",
    "fetch_local_file",
    "fetch_local_metadata",
    "fetch_remote_file",
    "fetch_remote_metadata",
    "GenerationValidationError",
    "GeneratorError",
    "InputDiscoveryError",
    "InvalidMetadataJSONError",
    "InvalidRepoURLError",
    "MANDATORY_FIELDS",
    "METADATA_FILENAME",
    "MetadataDiscoveryError",
    "MetadataFileNotFoundError",
    "MetadataNotFoundError",
    "RemoteResourceNotFoundError",
    "STANDARD_CONTEXT",
    "UnsupportedFormatError",
    "UnsupportedGeneratorError",
    "normalize_license_url",
    "parse_adapter_creator_string",
    "parse_dataset_creator_string",
    "parse_json_metadata",
    "slugify_identifier",
]
