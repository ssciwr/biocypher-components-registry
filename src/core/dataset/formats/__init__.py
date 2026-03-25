"""Format handlers used by the native dataset backend."""

from __future__ import annotations

from src.core.dataset.formats.base import FormatHandler
from src.core.dataset.formats.csv import CsvFormatHandler
from src.core.dataset.formats.csv_gz import CsvGzFormatHandler
from src.core.dataset.formats.parquet import ParquetFormatHandler
from src.core.dataset.formats.resolver import resolve_format_handler
from src.core.dataset.formats.tsv import TsvFormatHandler
from src.core.dataset.formats.tsv_gz import TsvGzFormatHandler

__all__ = [
    "CsvFormatHandler",
    "CsvGzFormatHandler",
    "FormatHandler",
    "ParquetFormatHandler",
    "TsvFormatHandler",
    "TsvGzFormatHandler",
    "resolve_format_handler",
]
