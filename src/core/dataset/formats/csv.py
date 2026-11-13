"""Independent inspector for plain CSV files."""

from __future__ import annotations

from pathlib import Path

from src.core.dataset.formats.base import (
    CSV_MIME,
    FormatHandler,
    inspect_delimited_file,
)
from src.core.dataset.request import FileInspection


class CsvFormatHandler(FormatHandler):
    """Inspect plain CSV files."""

    def supports(self, path: Path) -> bool:
        """Return whether the handler supports the given path."""
        return path.name.lower().endswith(".csv")

    def inspect(self, path: Path) -> FileInspection:
        """Inspect a CSV file and build a normalized schema snapshot."""
        return inspect_delimited_file(
            path=path,
            delimiter=",",
            encoding_format=CSV_MIME,
        )
