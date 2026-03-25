"""Inspector for Parquet files used by the native dataset backend."""

from __future__ import annotations

from pathlib import Path

from src.core.dataset.formats.base import PARQUET_MIME, FormatHandler, TEXT_TYPE
from src.core.dataset.request import FileInspection, InferredField
from src.core.shared.errors import UnsupportedFormatError


class ParquetFormatHandler(FormatHandler):
    """Inspect ``.parquet`` files using ``pyarrow``."""

    def supports(self, path: Path) -> bool:
        """Return whether the handler supports the given path."""
        return path.name.lower().endswith(".parquet")

    def inspect(self, path: Path) -> FileInspection:
        """Inspect a Parquet file and map Arrow types to Croissant types."""
        try:
            import pyarrow.parquet as pq
        except ModuleNotFoundError as exc:
            raise UnsupportedFormatError(
                "Parquet support requires the 'pyarrow' package to be installed."
            ) from exc

        table = pq.read_table(path)
        fields = [
            InferredField(
                name=field.name,
                data_type=_map_arrow_type(str(field.type)),
                examples=[],
            )
            for field in table.schema
        ]
        return FileInspection(
            path=path,
            encoding_format=PARQUET_MIME,
            fields=fields,
            examples_count=table.num_rows,
        )


def _map_arrow_type(arrow_type: str) -> str:
    """Map a pyarrow type name to a simple Croissant datatype."""
    normalized = arrow_type.lower()
    if "bool" in normalized:
        return "sc:Boolean"
    if any(token in normalized for token in ("int", "uint")):
        return "sc:Integer"
    if any(token in normalized for token in ("float", "double", "decimal")):
        return "sc:Float"
    return TEXT_TYPE
