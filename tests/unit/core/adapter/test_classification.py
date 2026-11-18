import jsonschema
import pytest

from src.core.adapter.document import build_adapter_document
from src.core.schema.profile import load_active_schema


def component_document():
    return build_adapter_document(
        name="Example",
        description="Example component",
        version="1.0.0",
        license_value="MIT",
        code_repository="https://example.org/repo",
        creators=[{"name": "Example author"}],
        keywords=["biology"],
        datasets=[{"@type": "sc:Dataset", "name": "Example dataset"}],
    )


@pytest.mark.parametrize(
    ("component_type", "granularity", "valid"),
    [
        ("adapter", "Primary", True),
        ("adapter", "Secondary", True),
        ("adapter", None, True),
        ("pipeline", "none", True),
        ("pipeline", None, True),
        (None, None, True),
        ("adapter", "none", False),
        ("pipeline", "Primary", False),
        ("pipeline", "Secondary", False),
        ("other", "Primary", False),
        ("adapter", "primary", False),
        (None, "none", False),
    ],
)
def test_component_classification_rules(component_type, granularity, valid):
    document = component_document()
    document.pop("componentType")
    if component_type is not None:
        document["componentType"] = component_type
    if granularity is not None:
        document["granularity"] = granularity
    errors = list(
        jsonschema.Draft7Validator(load_active_schema()).iter_errors(document)
    )
    assert (not errors) == valid
