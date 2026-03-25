"""Resolver for native dataset format handlers."""

from __future__ import annotations

from pathlib import Path

from src.core.dataset.formats.base import FormatHandler
from src.core.dataset.formats.csv import CsvFormatHandler
from src.core.dataset.formats.csv_gz import CsvGzFormatHandler
from src.core.dataset.formats.parquet import ParquetFormatHandler
from src.core.dataset.formats.tsv import TsvFormatHandler
from src.core.dataset.formats.tsv_gz import TsvGzFormatHandler
from src.core.shared.errors import UnsupportedFormatError


FORMAT_HANDLERS: list[FormatHandler] = [
    CsvGzFormatHandler(),
    TsvGzFormatHandler(),
    CsvFormatHandler(),
    TsvFormatHandler(),
    ParquetFormatHandler(),
]


def resolve_format_handler(path: Path) -> FormatHandler:
    """Return the first format handler that supports the given path."""
    for handler in FORMAT_HANDLERS:
        if handler.supports(path):
            return handler
    raise UnsupportedFormatError(f"Unsupported file format for '{path.name}'.")
