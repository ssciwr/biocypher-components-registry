"""CSV file inspection using ``croissant-baker``'s metadata extraction helpers."""

from __future__ import annotations

from pathlib import Path

from croissant_baker.handlers.csv_handler import CSVHandler

from src.core.dataset.formats.base import CSV_MIME, FormatHandler
from src.core.dataset.request import FileInspection, InferredField


class CsvFormatHandler(FormatHandler):
    """Inspect plain CSV files."""

    def supports(self, path: Path) -> bool:
        """Return whether the handler supports the given path."""
        return path.name.lower().endswith(".csv")

    def inspect(self, path: Path) -> FileInspection:
        """Inspect a CSV file and build a normalized schema snapshot."""
        metadata = CSVHandler().extract_metadata(path)
        fields = [
            InferredField(name=column, data_type=metadata["column_types"][column])
            for column in metadata["columns"]
        ]
        return FileInspection(
            path=path,
            encoding_format=CSV_MIME,
            fields=fields,
            examples_count=metadata.get("num_rows") or 0,
        )
