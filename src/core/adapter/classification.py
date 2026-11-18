"""BioCypher's software component classifications, distinct from Croissant data types."""

from enum import Enum


class AdapterGranularity(str, Enum):
    PRIMARY = "Primary"
    SECONDARY = "Secondary"


COMPONENT_TERMS = "https://biocypher.org/registry/terms/"
