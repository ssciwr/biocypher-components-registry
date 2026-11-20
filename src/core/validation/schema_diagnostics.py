"""Describe JSON Schema failures without parsing or rewriting validator messages."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator
from typing import Any

from jsonschema import ValidationError

from src.core.shared.json_source import JSONSource
from src.core.validation.results import ValidationDetail

_REQUIREMENTS = {
    "required": "Required property",
    "type": "Value type",
    "enum": "Allowed values",
    "const": "Required value",
    "pattern": "String pattern",
    "format": "String format",
    "minLength": "Minimum string length",
    "maxLength": "Maximum string length",
    "minItems": "Minimum number of items",
    "maxItems": "Maximum number of items",
    "uniqueItems": "Unique array items",
    "minimum": "Minimum value",
    "maximum": "Maximum value",
    "exclusiveMinimum": "Exclusive minimum value",
    "exclusiveMaximum": "Exclusive maximum value",
    "multipleOf": "Multiple of a value",
    "additionalProperties": "Allowed properties",
    "anyOf": "At least one allowed schema",
    "oneOf": "Exactly one allowed schema",
    "allOf": "All required schemas",
}


def _message(path: Iterable[str | int], message: str) -> str:
    location = " → ".join(str(part) for part in path)
    return f"[{location}] {message}" if location else message


def format_schema_error(error: ValidationError) -> str:
    """Keep the existing text error contract unchanged."""
    return _message(error.absolute_path, error.message)


def _json_path(path: Iterable[str | int]) -> str:
    result = "$"
    for part in path:
        if isinstance(part, int):
            result += f"[{part}]"
        elif re.fullmatch(r"[A-Za-z_]\w*", part, flags=re.ASCII):
            result += f".{part}"
        else:
            result += f"[{json.dumps(part, ensure_ascii=False)}]"
    return result


def _resolve(schema: Any, root: dict[str, Any]) -> dict[str, Any]:
    """Resolve only local references for descriptions; never fetch a schema."""
    visited = set()
    while isinstance(schema, dict) and "$ref" in schema:
        reference = schema["$ref"]
        if (
            not isinstance(reference, str)
            or not reference.startswith("#/")
            or reference in visited
        ):
            return {}
        visited.add(reference)
        target: Any = root
        for part in reference[2:].split("/"):
            key = part.replace("~1", "/").replace("~0", "~")
            if not isinstance(target, dict) or key not in target:
                return {}
            target = target[key]
        schema = target
    return schema if isinstance(schema, dict) else {}


def expected_format(schema: Any, root: dict[str, Any]) -> str | None:
    """Describe supplied primitive constraints; omit ambiguous schema alternatives."""
    schema = _resolve(schema, root)
    kind = schema.get("type")
    description = _type_description(schema, root)
    parts: list[str] = [description] if description else []

    for keyword, label in (
        ("enum", "Allowed values"),
        ("const", "Required value"),
        ("pattern", "Pattern"),
        ("format", "Format"),
        ("minLength", "Minimum characters"),
        ("maxLength", "Maximum characters"),
        ("minItems", "Minimum items"),
        ("maxItems", "Maximum items"),
        ("minimum", "Minimum"),
        ("maximum", "Maximum"),
        ("exclusiveMinimum", "Greater than"),
        ("exclusiveMaximum", "Less than"),
        ("multipleOf", "Multiple of"),
        ("minProperties", "Minimum properties"),
        ("maxProperties", "Maximum properties"),
    ):
        if keyword not in schema:
            continue
        if keyword == "minLength" and kind == "string" and schema[keyword] == 1:
            continue
        if keyword == "minItems" and kind == "array" and schema[keyword] == 1:
            continue
        parts.append(f"{label}: {json.dumps(schema[keyword], ensure_ascii=False)}")
    if schema.get("uniqueItems") is True:
        parts.append("Items must be unique")
    if schema.get("additionalProperties") is False:
        parts.append("No additional properties")
    return "; ".join(parts) or None


def _type_description(schema: dict[str, Any], root: dict[str, Any]) -> str | None:
    kind = schema.get("type")
    descriptions = {
        "string": "a non-empty string" if schema.get("minLength") == 1 else "a string",
        "integer": "an integer",
        "number": "a number",
        "boolean": "a boolean",
        "object": "an object",
        "array": "an array",
        "null": "null",
    }
    if isinstance(kind, list):
        return "Allowed types: " + ", ".join(kind)
    if not isinstance(kind, str) or kind not in descriptions:
        return None
    description = descriptions[kind]
    if kind == "array":
        description = _array_description(schema, root)
    return description[0].upper() + description[1:]


def _array_description(schema: dict[str, Any], root: dict[str, Any]) -> str:
    items = _resolve(schema.get("items"), root)
    item_kind = items.get("type")
    singular = None
    if isinstance(item_kind, str):
        singular = {
            "string": "non-empty string" if items.get("minLength") == 1 else "string",
            "integer": "integer",
            "number": "number",
            "object": "object",
            "boolean": "boolean",
        }.get(item_kind)
    if schema.get("minItems") == 1:
        return f"an array containing at least one {singular or 'item'}"
    if singular:
        return f"an array of {singular}s"
    return "an array"


def schema_validation_details(
    errors: Iterable[ValidationError],
    schema: dict[str, Any],
    source: JSONSource | None = None,
) -> list[ValidationDetail]:
    """Derive missing-field locations from constraints, never English error text."""
    details: list[ValidationDetail] = []
    seen: set[ValidationDetail] = set()
    missing_fields: dict[tuple[tuple, tuple], Iterator[str]] = {}
    for error in errors:
        detail = _schema_validation_detail(error, schema, source, missing_fields)
        if detail not in seen:
            seen.add(detail)
            details.append(detail)
    return details


def _schema_validation_detail(
    error: ValidationError,
    schema: dict[str, Any],
    source: JSONSource | None,
    missing_fields: dict[tuple[tuple, tuple], Iterator[str]],
) -> ValidationDetail:
    """Describe one error while sharing required-property order across errors."""
    path = list(error.absolute_path)
    source_path = tuple(path)
    location_kind = "value"
    container = _container_description(path)
    description = f"Check {container}."
    expected_schema = error.schema
    if error.validator == "required" and isinstance(error.instance, dict):
        # The required validator emits one error per missing property, in
        # constraint order. Pair those errors with structured missing names
        # while keeping each original message, including custom wording.
        key = (tuple(error.absolute_path), tuple(error.absolute_schema_path))
        missing = missing_fields.setdefault(
            key,
            iter(name for name in error.validator_value if name not in error.instance),
        )
        name = next(missing, None)
        if name is not None:
            path.append(name)
            location_kind = "containing_object"
            description = f"Add the missing field {json.dumps(name, ensure_ascii=False)} to {container}."
            expected_schema = error.schema.get("properties", {}).get(name)
        else:
            expected_schema = None
    position = source.value_position(source_path) if source else None
    return ValidationDetail(
        message=format_schema_error(error),
        json_path=_json_path(path),
        requirement=_REQUIREMENTS.get(error.validator, error.validator),
        expected_format=expected_format(expected_schema, schema),
        location_description=description,
        source_file=source.filename if source else None,
        source_url=source.url if source else None,
        line=position[0] if position else None,
        column=position[1] if position else None,
        location_kind=location_kind,
    )


def _container_description(path: list[str | int]) -> str:
    if not path:
        return "the top-level object (inside the outer { ... } braces)"
    return "the top-level object → " + " → ".join(
        f"item {part + 1}"
        if isinstance(part, int)
        else f"field {json.dumps(part, ensure_ascii=False)}"
        for part in path
    )
