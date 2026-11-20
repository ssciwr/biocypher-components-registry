"""Source positions refer to the original JSON, never a reformatted document."""

import pytest

from src.core.shared.json_source import JSONSource


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
