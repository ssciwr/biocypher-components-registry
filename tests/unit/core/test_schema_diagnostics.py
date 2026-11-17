"""Validator context remains optional and never replaces existing error text."""

import json

import pytest
from jsonschema import Draft7Validator, ValidationError

from src.core.shared.json_source import JSONSource
from src.core.validation.adapter import validate_adapter_with_embedded_datasets
from src.core.validation.schema_diagnostics import (
    expected_format,
    format_schema_error,
    schema_validation_details,
)
from tests.support.croissant_fixtures import sample_adapter_document


def test_missing_properties_keep_legacy_messages_and_describe_the_target_fields():
    document = sample_adapter_document()
    document.pop("keywords")
    document.pop("license")
    result = validate_adapter_with_embedded_datasets(document)
    details = {detail.json_path: detail for detail in result.validation_details}
    assert set(details) == {"$.keywords", "$.license"}
    assert [detail.message for detail in result.validation_details] == result.errors
    assert details["$.keywords"].message == "'keywords' is a required property"
    assert details["$.keywords"].requirement == "Required property"
    assert (
        details["$.keywords"].expected_format
        == "An array containing at least one non-empty string"
    )
    assert details["$.license"].expected_format == "A non-empty string"


@pytest.mark.parametrize(
    "value, expected_path", [([{}], "$.people[0].name"), ({}, "$.people.name")]
)
def test_nested_missing_fields_include_their_full_location(value, expected_path):
    person = {
        "type": "object",
        "required": ["name"],
        "properties": {"name": {"type": "string", "minLength": 1}},
    }
    schema = {
        "properties": {
            "people": {"type": "array", "items": person}
            if isinstance(value, list)
            else person
        }
    }
    errors = list(Draft7Validator(schema).iter_errors({"people": value}))
    details = schema_validation_details(errors, schema)
    assert len(details) == 1
    assert details[0].json_path == expected_path
    assert details[0].requirement == "Required property"
    assert details[0].expected_format == "A non-empty string"
    assert details[0].message == format_schema_error(errors[0])


@pytest.mark.parametrize(
    "name",
    [
        "odd.name",
        "quote'key",
        'double"quote',
        "@id",
        "path\\key",
        "a/b",
        "naïve",
        "用户",
        "a١",
    ],
)
def test_json_locations_escape_property_names_without_losing_the_original_message(name):
    schema = {"properties": {name: {"type": "string"}}}
    errors = list(Draft7Validator(schema).iter_errors({name: 42}))
    detail = schema_validation_details(errors, schema)[0]
    assert detail.json_path == f"$[{json.dumps(name, ensure_ascii=False)}]"
    assert detail.message == format_schema_error(errors[0])
    assert detail.requirement == "Value type"


def test_array_item_type_error_includes_index_and_expected_type():
    schema = {
        "properties": {"keywords": {"type": "array", "items": {"type": "string"}}}
    }
    errors = list(Draft7Validator(schema).iter_errors({"keywords": [42]}))
    detail = schema_validation_details(errors, schema)[0]
    assert detail.json_path == "$.keywords[0]"
    assert detail.requirement == "Value type"
    assert detail.expected_format == "A string"
    assert detail.message == "[keywords → 0] 42 is not of type 'string'"


def test_required_field_context_does_not_depend_on_english_error_wording():
    schema = {"required": ["name"], "properties": {"name": {"type": "string"}}}
    error = ValidationError(
        "Custom validator wording remains intact.",
        validator="required",
        validator_value=["name"],
        instance={},
        schema=schema,
    )
    detail = schema_validation_details([error], schema)[0]
    assert detail.message == error.message
    assert detail.json_path == "$.name"
    assert detail.expected_format == "A string"


def test_required_fields_stay_paired_with_their_object_and_schema_branch():
    person = {
        "allOf": [
            {
                "required": ["name", "age"],
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
            },
            {
                "required": ["license"],
                "properties": {"license": {"type": "string", "minLength": 1}},
            },
        ]
    }
    schema = {"properties": {"people": {"type": "array", "items": person}}}
    text = '{\n "people": [\n  {},\n  {"name": "Ada"}\n ]\n}'
    source = JSONSource(text, "croissant.jsonld")
    errors = list(Draft7Validator(schema).iter_errors(json.loads(text)))
    for error in errors:
        error.message = "Custom required-property diagnostic."

    details = schema_validation_details(iter(errors), schema, source)

    assert [detail.json_path for detail in details] == [
        "$.people[0].name",
        "$.people[0].age",
        "$.people[0].license",
        "$.people[1].age",
        "$.people[1].license",
    ]
    assert [detail.expected_format for detail in details] == [
        "A string",
        "An integer",
        "A non-empty string",
        "An integer",
        "A non-empty string",
    ]
    assert [(detail.line, detail.column) for detail in details] == [
        (3, 3),
        (3, 3),
        (3, 3),
        (4, 3),
        (4, 3),
    ]
    assert all(detail.location_kind == "containing_object" for detail in details)
    assert all("item 1" in detail.location_description for detail in details[:3])
    assert all("item 2" in detail.location_description for detail in details[3:])
    assert [detail.message for detail in details] == [
        format_schema_error(error) for error in errors
    ]


def test_duplicate_details_are_removed_without_changing_error_order():
    schema = {"properties": {"name": {"type": "string"}, "age": {"type": "integer"}}}
    errors = list(Draft7Validator(schema).iter_errors({"name": 42, "age": "old"}))

    details = schema_validation_details(
        iter([errors[0], errors[0], errors[1], errors[0]]), schema
    )

    assert [detail.json_path for detail in details] == ["$.name", "$.age"]
    assert [detail.message for detail in details] == [
        format_schema_error(error) for error in errors
    ]
    assert all(detail.location_kind == "value" for detail in details)
    assert all(detail.line is None and detail.column is None for detail in details)


@pytest.mark.parametrize(
    "schema, value, requirement, expected",
    [
        (
            {"type": "string", "enum": ["alpha", "beta"]},
            "other",
            "Allowed values",
            'Allowed values: ["alpha", "beta"]',
        ),
        (
            {"type": "string", "pattern": "^[A-Z]+$"},
            "lower",
            "String pattern",
            'Pattern: "^[A-Z]+$"',
        ),
        (
            {"type": "string", "minLength": 3},
            "a",
            "Minimum string length",
            "Minimum characters: 3",
        ),
        (
            {"type": "string", "maxLength": 3},
            "longer",
            "Maximum string length",
            "Maximum characters: 3",
        ),
        (
            {"type": "array", "maxItems": 1},
            [1, 2],
            "Maximum number of items",
            "Maximum items: 1",
        ),
        ({"type": "number", "minimum": 2}, 1, "Minimum value", "Minimum: 2"),
        (
            {"type": "number", "exclusiveMaximum": 2},
            2,
            "Exclusive maximum value",
            "Less than: 2",
        ),
        (
            {"type": "integer", "multipleOf": 2},
            3,
            "Multiple of a value",
            "Multiple of: 2",
        ),
        ({"const": "fixed"}, "other", "Required value", 'Required value: "fixed"'),
    ],
)
def test_constraint_information_comes_from_the_schema(
    schema, value, requirement, expected
):
    errors = list(Draft7Validator(schema).iter_errors(value))
    detail = schema_validation_details(errors, schema)[0]
    assert detail.json_path == "$"
    assert detail.requirement == requirement
    assert expected in detail.expected_format
    assert detail.message == errors[0].message


@pytest.mark.parametrize(
    "schema, expected",
    [
        ({"type": "string", "minLength": 1}, "A non-empty string"),
        ({"type": ["string", "null"]}, "Allowed types: string, null"),
        ({"type": "array", "items": {"type": "integer"}}, "An array of integers"),
        (
            {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
                "minItems": 1,
            },
            "An array containing at least one non-empty string",
        ),
        (
            {"type": "array", "items": {"type": ["string", "null"]}, "minItems": 1},
            "An array containing at least one item",
        ),
        ({"type": "array", "items": {"type": "null"}}, "An array"),
        (
            {"type": "array", "minItems": 2, "uniqueItems": True},
            "An array; Minimum items: 2; Items must be unique",
        ),
        (
            {"type": "object", "additionalProperties": False},
            "An object; No additional properties",
        ),
        ({}, None),
        (False, None),
    ],
)
def test_expected_format_preserves_complete_type_and_constraint_descriptions(
    schema, expected
):
    assert expected_format(schema, {}) == expected


@pytest.mark.parametrize(
    "reference, expected",
    [
        ("#/definitions/name", "A non-empty string"),
        ("#/definitions/loop", None),
        ("https://example.invalid/schema", None),
    ],
)
def test_missing_field_descriptions_resolve_local_refs_but_never_follow_remote_or_cyclic_refs(
    reference, expected
):
    schema = {
        "required": ["name"],
        "properties": {"name": {"$ref": reference}},
        "definitions": {
            "name": {"type": "string", "minLength": 1},
            "loop": {"$ref": "#/definitions/loop"},
        },
    }
    errors = list(Draft7Validator(schema).iter_errors({}))
    detail = schema_validation_details(errors, schema)[0]
    assert detail.json_path == "$.name"
    assert detail.expected_format == expected


def test_text_only_croissant_errors_are_preserved_without_invented_context(monkeypatch):
    monkeypatch.setattr(
        "src.core.validation.adapter.validate_with_mlcroissant",
        lambda _: ["Croissant problem"],
    )
    result = validate_adapter_with_embedded_datasets(sample_adapter_document())
    assert "Croissant problem" in result.errors
    assert result.validation_details == []
