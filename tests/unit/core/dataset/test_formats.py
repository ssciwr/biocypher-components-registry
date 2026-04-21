from __future__ import annotations

from pathlib import Path

import pytest

from src.core.dataset.formats.csv import CsvFormatHandler
from src.core.dataset.formats.csv_gz import CsvGzFormatHandler
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
