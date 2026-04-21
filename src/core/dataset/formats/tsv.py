"""Inspector for plain TSV files."""

from __future__ import annotations

from pathlib import Path

from src.core.dataset.formats.base import TSV_MIME, FormatHandler, inspect_delimited_file
from src.core.dataset.request import FileInspection


class TsvFormatHandler(FormatHandler):
    """Inspect ``.tsv`` files."""

    def supports(self, path: Path) -> bool:
        """Return whether the handler supports the given path."""
        return path.name.lower().endswith(".tsv")

    def inspect(self, path: Path) -> FileInspection:
        """Inspect a tab-separated text file."""
        return inspect_delimited_file(path=path, delimiter="\t", encoding_format=TSV_MIME)
