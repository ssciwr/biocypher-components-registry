from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from src.core.dataset.formats.csv import CsvFormatHandler
from src.core.dataset.formats.csv_gz import CsvGzFormatHandler
from src.core.dataset.formats.parquet import ParquetFormatHandler
from src.core.dataset.formats.resolver import resolve_format_handler
from src.core.dataset.formats.tsv import TsvFormatHandler
from src.core.dataset.formats.tsv_gz import TsvGzFormatHandler
from src.core.shared.errors import UnsupportedFormatError


def test_resolve_format_handler_returns_expected_types() -> None:
    assert isinstance(resolve_format_handler(Path("data.csv")), CsvFormatHandler)
    assert isinstance(resolve_format_handler(Path("data.csv.gz")), CsvGzFormatHandler)
    assert isinstance(resolve_format_handler(Path("data.tsv")), TsvFormatHandler)
    assert isinstance(resolve_format_handler(Path("data.tsv.gz")), TsvGzFormatHandler)


def test_resolve_format_handler_raises_for_unknown_format() -> None:
    with pytest.raises(UnsupportedFormatError):
        resolve_format_handler(Path("data.json"))


def test_parquet_inspection_reads_schema_metadata_without_loading_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parquet_path = tmp_path / "data.parquet"
    parquet_path.write_bytes(b"fixture")

    class FakeParquetFile:
        schema_arrow = [SimpleNamespace(name="id", type="int64")]
        metadata = SimpleNamespace(num_rows=12)

        def __init__(self, path: Path) -> None:
            assert path == parquet_path

    package = ModuleType("pyarrow")
    package.__path__ = []  # type: ignore[attr-defined]
    parquet = ModuleType("pyarrow.parquet")
    parquet.ParquetFile = FakeParquetFile  # type: ignore[attr-defined]
    parquet.read_table = lambda _path: pytest.fail("full table must not be loaded")  # type: ignore[attr-defined]
    package.parquet = parquet  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pyarrow", package)
    monkeypatch.setitem(sys.modules, "pyarrow.parquet", parquet)

    inspection = ParquetFormatHandler().inspect(parquet_path)

    assert inspection.examples_count == 12
    assert inspection.fields[0].data_type == "sc:Integer"
