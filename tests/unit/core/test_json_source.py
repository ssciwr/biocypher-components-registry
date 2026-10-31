"""Source positions refer to the original JSON, never a reformatted document."""

import json

import pytest
from jsonschema import Draft7Validator

from src.core.shared.errors import InvalidMetadataJSONError
from src.core.shared.files import parse_json_metadata
from src.core.shared.json_source import JSONSource
from src.core.validation.adapter import validate_adapter_with_embedded_datasets
from src.core.validation.schema_diagnostics import schema_validation_details
from tests.support.croissant_fixtures import sample_adapter_document


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_original_line_and_column_positions_include_blank_lines_and_array_indexes(
    newline,
):
    text = newline.join(
        ["", "{", '  "keywords": [', "    42", "  ],", '  "name": "Adapter"', "}"]
    )
    source = JSONSource(text, "croissant.jsonld")
    assert source.value_position(()) == (2, 1)
    assert source.value_position(("keywords",)) == (3, 15)
    assert source.value_position(("keywords", 0)) == (4, 5)
    assert source.value_position(("name",)) == (6, 11)
    assert source.value_position(("missing",)) is None


def test_escaped_keys_and_braces_inside_strings_do_not_confuse_source_positions():
    text = r'{"label": "{not a field}", "\u006eame": {"quote\"key": 42}}'
    source = JSONSource(text, "croissant.jsonld")
    assert source.value_position(("name", 'quote"key')) == (1, text.index("42") + 1)


def test_duplicate_keys_follow_the_same_last_value_rule_as_json_loads():
    source = JSONSource('{\n "name": 1,\n "name": false\n}', "croissant.jsonld")
    assert source.value_position(("name",)) == (3, 10)


@pytest.mark.parametrize(
    "value", ["{}", "[]", '"escaped\\ntext"', "42", "-1.5e2", "true", "false", "null"]
)
def test_root_values_retain_their_original_offsets(value):
    source = JSONSource(f" \n  {value}\n", "croissant.jsonld")
    assert source.value_offsets == {(): 4}
    assert source.value_position(()) == (2, 3)


def test_nested_containers_and_siblings_retain_all_value_offsets():
    text = '{"items": [ {}, [], {"values": [true, null]}, 42 ], "end": false}'
    source = JSONSource(text, "croissant.jsonld")
    assert source.value_offsets == {
        (): 0,
        ("items",): text.index("["),
        ("items", 0): text.index("{}"),
        ("items", 1): text.index("[]"),
        ("items", 2): text.index('{"values"'),
        ("items", 2, "values"): text.index("[true"),
        ("items", 2, "values", 0): text.index("true"),
        ("items", 2, "values", 1): text.index("null"),
        ("items", 3): text.index("42"),
        ("end",): text.index("false"),
    }
    assert source.value_offsets is source.value_offsets


@pytest.mark.parametrize(
    "text", ['{"value": invalid}', '{"value": ', "[" * 2000 + "]" * 2000]
)
def test_traversal_failure_discards_partial_offsets(text):
    source = JSONSource(text, "croissant.jsonld")
    assert source.value_offsets == {}
    assert source.value_position(()) is None


def test_wrong_values_have_exact_positions_and_readable_array_locations():
    text = '\n{\n  "keywords": [\n    42\n  ]\n}'
    schema = {
        "properties": {"keywords": {"type": "array", "items": {"type": "string"}}}
    }
    source = JSONSource(
        text,
        "croissant.jsonld",
        "https://github.com/org/repo/blob/commit/croissant.jsonld",
    )
    errors = list(Draft7Validator(schema).iter_errors(json.loads(text)))
    detail = schema_validation_details(errors, schema, source)[0]
    assert detail.json_path == "$.keywords[0]"
    assert (detail.line, detail.column) == (4, 5)
    assert detail.location_kind == "value"
    assert "item 1" in detail.location_description
    assert detail.source_file == "croissant.jsonld"
    assert detail.source_url == source.url


def test_missing_fields_point_to_the_containing_object_without_inventing_a_field_line():
    document = sample_adapter_document()
    document.pop("keywords")
    text = "\n\n" + json.dumps(document, indent=2)
    metadata = parse_json_metadata(text, "repository")
    assert json.loads(json.dumps(metadata)) == document
    assert "json_source" not in metadata
    result = validate_adapter_with_embedded_datasets(metadata)
    detail = next(
        detail
        for detail in result.validation_details
        if detail.json_path == "$.keywords"
    )
    assert detail.location_kind == "containing_object"
    assert (detail.line, detail.column) == (3, 1)
    assert 'Add the missing field "keywords"' in detail.location_description
    assert "top-level object" in detail.location_description
    assert "outer { ... } braces" in detail.location_description


def test_invalid_json_retains_the_parsers_exact_line_and_column():
    with pytest.raises(InvalidMetadataJSONError) as caught:
        parse_json_metadata('{\n  "keywords": [1,]\n}', "repository")
    import json

    with pytest.raises(json.JSONDecodeError) as parser_error:
        json.loads('{\n  "keywords": [1,]\n}')
    assert caught.value.line == parser_error.value.lineno
    assert caught.value.column == parser_error.value.colno
    assert caught.value.source_file == "croissant.jsonld"


def test_plain_dictionary_validation_does_not_invent_source_positions():
    document = sample_adapter_document()
    document.pop("keywords")
    detail = validate_adapter_with_embedded_datasets(document).validation_details[0]
    assert detail.line is None
    assert detail.column is None
    assert "top-level object" in detail.location_description
