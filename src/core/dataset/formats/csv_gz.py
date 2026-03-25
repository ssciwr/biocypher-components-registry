"""Inspector for gzip-compressed CSV files."""

from __future__ import annotations

from pathlib import Path

from src.core.dataset.formats.base import CSV_MIME, FormatHandler, inspect_delimited_file
from src.core.dataset.request import FileInspection


class CsvGzFormatHandler(FormatHandler):
    """Inspect ``.csv.gz`` files."""

    def supports(self, path: Path) -> bool:
        """Return whether the handler supports the given path."""
        return path.name.lower().endswith(".csv.gz")

    def inspect(self, path: Path) -> FileInspection:
        """Inspect a gzip-compressed CSV file."""
        return inspect_delimited_file(
            path=path,
            delimiter=",",
            encoding_format=CSV_MIME,
            compressed=True,
        )
