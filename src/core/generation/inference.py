"""Automatic field inference from tabular data files.

Reads a CSV or TSV file (plain or gzip-compressed) and produces a list
of Croissant ``cr:Field`` dicts by inspecting column headers, pandas
series types, and example values.
"""

from __future__ import annotations

import csv
import gzip
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd

TEXT_TYPE = "sc:Text"
INTEGER_TYPE = "sc:Integer"
FLOAT_TYPE = "sc:Float"
BOOLEAN_TYPE = "sc:Boolean"
CSV_MIME = "text/csv"
TSV_MIME = "text/tab-separated-values"

_DTYPE_MAP: Dict[str, str] = {
    "O": TEXT_TYPE,
    "U": TEXT_TYPE,
    "S": TEXT_TYPE,
    "i": INTEGER_TYPE,
    "u": INTEGER_TYPE,
    "f": FLOAT_TYPE,
    "b": BOOLEAN_TYPE,
    "M": TEXT_TYPE,
    "m": TEXT_TYPE,
}

_ENCODING_FORMAT_MAP: Dict[str, str] = {
    ".csv": CSV_MIME,
    ".tsv": TSV_MIME,
    ".tab": TSV_MIME,
}


def infer_fields_from_file(
    file_path: str | Path,
    record_set_id: str,
    file_object_id: str,
    max_rows: int = 500,
    n_examples: int = 1,
) -> Tuple[List[Dict[str, Any]], str]:
    """Infer Croissant field definitions from a local tabular data file."""
    path = Path(file_path)
    encoding_format, sep = _detect_format(path)

    try:
        df = pd.read_csv(path, sep=sep, nrows=max_rows, low_memory=False)
    except Exception as exc:
        raise ValueError(f"Could not read {path}: {exc}") from exc

    fields: List[Dict[str, Any]] = []
    for col in df.columns:
        series = df[col]
        data_type = _dtype_to_croissant(series.dtype)
        examples = _extract_examples(series, n_examples)
        fields.append(
            {
                "@type": "cr:Field",
                "@id": f"{record_set_id}/{col}",
                "name": col,
                "description": "",
                "dataType": data_type,
                "examples": examples,
                "source": {
                    "fileObject": {"@id": file_object_id},
                    "extract": {"column": col},
                },
            }
        )

    return fields, encoding_format


def _detect_format(path: Path) -> Tuple[str, str]:
    name = path.name.lower()
    if name.endswith(".gz"):
        name = name[:-3]

    suffix = Path(name).suffix
    encoding_format = _ENCODING_FORMAT_MAP.get(suffix)
    if encoding_format is None:
        raise ValueError(
            f"Unsupported file format '{suffix}'. "
            "Supported: .csv, .tsv, .tab (optionally gzip-compressed)."
        )

    sample = _read_sample(path)
    sep = _detect_separator(sample, default=_separator_from_suffix(suffix))
    return _encoding_format_from_separator(sep), sep


def _read_sample(path: Path, size: int = 8192) -> str:
    opener = gzip.open if path.name.lower().endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as handle:
        return handle.read(size)


def _detect_separator(sample: str, default: str) -> str:
    header = _first_non_empty_line(sample)
    if header:
        comma_count = header.count(",")
        tab_count = header.count("\t")
        if tab_count > comma_count:
            return "\t"
        if comma_count > tab_count:
            return ","

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t")
        return dialect.delimiter
    except csv.Error:
        comma_count = sample.count(",")
        tab_count = sample.count("\t")
        if tab_count > comma_count:
            return "\t"
        if comma_count > tab_count:
            return ","
        return default


def _first_non_empty_line(sample: str) -> str:
    for line in sample.splitlines():
        if line.strip():
            return line
    return ""


def _separator_from_suffix(suffix: str) -> str:
    return "\t" if suffix in {".tsv", ".tab"} else ","


def _encoding_format_from_separator(separator: str) -> str:
    if separator == "\t":
        return TSV_MIME
    return CSV_MIME


def _dtype_to_croissant(dtype: Any) -> str:
    return _DTYPE_MAP.get(getattr(dtype, "kind", "O"), TEXT_TYPE)


def _extract_examples(series: Any, n: int = 1) -> List[Any]:
    seen: List[Any] = []
    for val in series.dropna():
        native = val.item() if hasattr(val, "item") else val
        if native not in seen:
            seen.append(native)
        if len(seen) >= n:
            break
    return seen
