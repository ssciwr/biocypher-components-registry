"""Base utilities for inspecting tabular dataset file formats."""

from __future__ import annotations

import csv
import gzip
from abc import ABC, abstractmethod
from pathlib import Path

from src.core.dataset.request import FileInspection, InferredField


TEXT_TYPE = "sc:Text"
INTEGER_TYPE = "sc:Integer"
FLOAT_TYPE = "sc:Float"
BOOLEAN_TYPE = "sc:Boolean"
CSV_MIME = "text/csv"
TSV_MIME = "text/tab-separated-values"
PARQUET_MIME = "application/vnd.apache.parquet"


class FormatHandler(ABC):
    """Interface implemented by concrete file format inspectors."""

    @abstractmethod
    def supports(self, path: Path) -> bool:
        """Return whether the handler can inspect this file."""

    @abstractmethod
    def inspect(self, path: Path) -> FileInspection:
        """Inspect a file and return a normalized schema snapshot."""


def inspect_delimited_file(
    path: Path,
    delimiter: str,
    encoding_format: str,
    compressed: bool = False,
    max_rows: int = 500,
    n_examples: int = 1,
) -> FileInspection:
    """Inspect a delimited text file and infer its fields.

    Args:
        path: File to inspect.
        delimiter: Column separator to use.
        encoding_format: MIME type stored in the result.
        compressed: Whether the file is gzip-compressed.
        max_rows: Maximum number of rows to sample.
        n_examples: Number of unique examples to keep per field.

    Returns:
        A normalized file inspection result.
    """
    opener = gzip.open if compressed else open
    with opener(path, "rt", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        if reader.fieldnames is None:
            raise ValueError(f"Could not detect columns in {path}.")

        fieldnames = [str(name) for name in reader.fieldnames]
        samples: dict[str, list[str]] = {name: [] for name in fieldnames}
        row_count = 0
        for row in reader:
            row_count += 1
            for field in fieldnames:
                value = row.get(field, "")
                if value is not None and value != "":
                    samples[field].append(str(value))
            if row_count >= max_rows:
                break

    fields = [
        InferredField(
            name=field,
            data_type=_infer_data_type(samples[field]),
            examples=_collect_examples(samples[field], n_examples),
        )
        for field in fieldnames
    ]
    return FileInspection(
        path=path,
        encoding_format=encoding_format,
        fields=fields,
        examples_count=row_count,
    )


def _collect_examples(values: list[str], n_examples: int) -> list[str]:
    """Collect the first unique example values for a field."""
    seen: list[str] = []
    for value in values:
        if value not in seen:
            seen.append(value)
        if len(seen) >= n_examples:
            break
    return seen


def _infer_data_type(values: list[str]) -> str:
    """Infer a simple Croissant datatype from sampled string values."""
    if not values:
        return TEXT_TYPE
    if all(_is_boolean(value) for value in values):
        return BOOLEAN_TYPE
    if all(_is_integer(value) for value in values):
        return INTEGER_TYPE
    if all(_is_float(value) for value in values):
        return FLOAT_TYPE
    return TEXT_TYPE


def _is_boolean(value: str) -> bool:
    """Return whether a value looks boolean-like."""
    return value.strip().lower() in {"true", "false", "0", "1", "yes", "no"}


def _is_integer(value: str) -> bool:
    """Return whether a value can be parsed as an integer."""
    try:
        int(value)
        return True
    except ValueError:
        return False


def _is_float(value: str) -> bool:
    """Return whether a value can be parsed as a float."""
    try:
        float(value)
        return True
    except ValueError:
        return False
