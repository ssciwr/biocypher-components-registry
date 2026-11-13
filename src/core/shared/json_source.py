"""Original JSON text and value positions, kept outside serialized metadata."""

from __future__ import annotations

import bisect
import json
import re
from dataclasses import dataclass
from functools import cached_property
from typing import Any


class _JSONOffsetIndexer:
    """Traverse JSON containers while retaining original value offsets."""

    def __init__(self, text: str):
        self.text = text
        self.decoder = json.JSONDecoder()
        self.whitespace = re.compile(r"[ \t\r\n]*")
        self.offsets: dict[tuple[str | int, ...], int] = {}

    def skip(self, offset: int) -> int:
        return self.whitespace.match(self.text, offset).end()

    def visit_object(self, offset: int, path: tuple[str | int, ...]) -> int:
        offset = self.skip(offset + 1)
        if self.text[offset] == "}":
            return offset + 1
        while True:
            key, offset = self.decoder.raw_decode(self.text, offset)
            offset = self.visit(self.skip(offset) + 1, (*path, key))
            offset = self.skip(offset)
            if self.text[offset] == "}":
                return offset + 1
            offset = self.skip(offset + 1)

    def visit_array(self, offset: int, path: tuple[str | int, ...]) -> int:
        offset = self.skip(offset + 1)
        if self.text[offset] == "]":
            return offset + 1
        index = 0
        while True:
            offset = self.skip(self.visit(offset, (*path, index)))
            if self.text[offset] == "]":
                return offset + 1
            offset = self.skip(offset + 1)
            index += 1

    def visit(self, offset: int, path: tuple[str | int, ...]) -> int:
        offset = self.skip(offset)
        self.offsets[path] = offset
        kind = self.text[offset]
        if kind == "{":
            return self.visit_object(offset, path)
        if kind == "[":
            return self.visit_array(offset, path)
        return self.decoder.raw_decode(self.text, offset)[1]


@dataclass
class JSONSource:
    text: str
    filename: str
    url: str | None = None

    @cached_property
    def _line_starts(self) -> list[int]:
        return [0, *(match.end() for match in re.finditer("\n", self.text))]

    def position(self, offset: int) -> tuple[int, int]:
        line = bisect.bisect_right(self._line_starts, offset)
        return line, offset - self._line_starts[line - 1] + 1

    @cached_property
    def value_offsets(self) -> dict[tuple[str | int, ...], int]:
        """Index the already validated source using the standard JSON decoder.

        Container traversal preserves offsets; string escapes and primitives
        are decoded by Python's JSON decoder. Duplicate keys follow json.loads
        semantics: the last value supplies the position used by validation.
        """
        indexer = _JSONOffsetIndexer(self.text)
        try:
            indexer.visit(0, ())
        except (ValueError, IndexError, RecursionError):
            # Source enrichment must never change validation or acceptance.
            return {}
        return indexer.offsets

    def value_position(self, path: tuple[str | int, ...]) -> tuple[int, int] | None:
        offset = self.value_offsets.get(path)
        return self.position(offset) if offset is not None else None


class MetadataDocument(dict[str, Any]):
    """A normal metadata dict with non-serialized original-source provenance."""

    def __init__(self, data: dict[str, Any], source: JSONSource):
        super().__init__(data)
        self.json_source = source
