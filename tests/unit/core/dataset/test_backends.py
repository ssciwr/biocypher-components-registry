from __future__ import annotations

import json

import pytest

from src.core.dataset.backends import auto_select, list_generators, resolve_generator
from src.core.dataset.backends.auto_select import (
    AutoDatasetGenerator,
    select_generator,
)
from src.core.dataset.backends.croissant_baker import (
    CroissantBakerGenerator,
    _has_report_option,
    _read_scan_warnings,
)
from src.core.dataset.backends.native import NativeDatasetGenerator
from src.core.dataset.formats.csv import CsvFormatHandler
from src.core.dataset.request import GenerationRequest
from src.core.shared.errors import UnsupportedFormatError, UnsupportedGeneratorError


class NativeOnlyCsvFormatHandler(CsvFormatHandler):
    croissant_baker_supported = False


def test_generation_request_validates_by_default() -> None:
    request = GenerationRequest(
        input_path="/data/example.csv", output_path="out.jsonld"
    )

    assert request.validate is True


def test_list_generators_contains_expected_backends() -> None:
    assert list_generators() == ["auto", "croissant-baker", "native"]


def test_resolve_generator_returns_known_implementations() -> None:
    assert isinstance(resolve_generator("auto"), AutoDatasetGenerator)
    assert isinstance(resolve_generator("croissant-baker"), CroissantBakerGenerator)
    assert isinstance(resolve_generator("native"), NativeDatasetGenerator)


def test_resolve_generator_raises_for_unknown_name() -> None:
    with pytest.raises(UnsupportedGeneratorError):
        resolve_generator("missing")


@pytest.mark.parametrize(
    "filename",
    [
        "records.csv",
        "records.tsv",
        "records.csv.gz",
        "records.tsv.gz",
        "records.parquet",
    ],
)
def test_auto_prefers_croissant_baker_for_shared_formats(
    tmp_path, filename: str
) -> None:
    input_path = tmp_path / filename
    input_path.touch()
    request = GenerationRequest(
        input_path=str(input_path),
        output_path=str(tmp_path / "metadata.jsonld"),
    )

    generator, reason = select_generator(request)

    assert isinstance(generator, CroissantBakerGenerator)
    assert "preferred backend" in reason


def test_auto_selects_native_for_a_native_only_format(tmp_path, monkeypatch) -> None:
    input_path = tmp_path / "records.native-only"
    input_path.touch()
    request = GenerationRequest(
        input_path=str(input_path),
        output_path=str(tmp_path / "metadata.jsonld"),
    )
    native_only_handler = NativeOnlyCsvFormatHandler()
    monkeypatch.setattr(
        auto_select,
        "resolve_format_handler",
        lambda _path: native_only_handler,
    )

    generator, reason = select_generator(request)

    assert isinstance(generator, NativeDatasetGenerator)
    assert "Croissant Baker does not support" in reason


def test_auto_keeps_baker_for_mixed_native_and_non_native_inputs(
    tmp_path, monkeypatch
) -> None:
    (tmp_path / "records.native-only").touch()
    (tmp_path / "notes.txt").touch()
    request = GenerationRequest(
        input_path=str(tmp_path),
        output_path=str(tmp_path / "metadata.jsonld"),
    )

    def resolve_native_handler(path):
        if path.name.endswith(".native-only"):
            return native_only_handler
        raise UnsupportedFormatError(f"Unsupported file: {path.name}")

    native_only_handler = NativeOnlyCsvFormatHandler()
    monkeypatch.setattr(auto_select, "resolve_format_handler", resolve_native_handler)

    generator, _ = select_generator(request)

    assert isinstance(generator, CroissantBakerGenerator)


def test_auto_does_not_fallback_after_baker_execution_failure(
    monkeypatch, tmp_path
) -> None:
    request = GenerationRequest(
        input_path=str(tmp_path / "records.csv"),
        output_path=str(tmp_path / "metadata.jsonld"),
    )

    class FailingBaker:
        name = "croissant-baker"

        def generate(self, _request):
            raise RuntimeError("Baker failed.")

    monkeypatch.setattr(
        auto_select, "select_generator", lambda _request: (FailingBaker(), "test")
    )

    with pytest.raises(RuntimeError, match="Baker failed"):
        AutoDatasetGenerator().generate(request)


@pytest.mark.parametrize("outcome", ["described", "linked", "referenced"])
def test_baker_scan_accepts_every_document_coverage_outcome(
    tmp_path, outcome: str
) -> None:
    report_path = tmp_path / "report.json"
    report_path.write_text(
        json.dumps({"files": [{"path": "data", "outcome": outcome}]}),
        encoding="utf-8",
    )

    assert _read_scan_warnings(report_path) == []


@pytest.mark.parametrize("outcome", ["unclaimed", "failed", "pending"])
def test_baker_scan_warns_about_omitted_or_nonterminal_files(
    tmp_path, outcome: str
) -> None:
    report_path = tmp_path / "report.json"
    report_path.write_text(
        json.dumps({"files": [{"path": "data", "outcome": outcome}]}),
        encoding="utf-8",
    )

    assert _read_scan_warnings(report_path) == [
        "Croissant Baker did not describe 1 discovered file(s)."
    ]


def test_baker_scan_warns_about_diagnostics(tmp_path) -> None:
    report_path = tmp_path / "report.json"
    report_path.write_text(
        json.dumps(
            {
                "files": [
                    {
                        "path": "data.xlsx",
                        "outcome": "described",
                        "diagnostics": [{"code": "sheet_skipped"}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    assert _read_scan_warnings(report_path) == [
        "Croissant Baker reported 1 non-fatal diagnostic(s)."
    ]


@pytest.mark.parametrize(
    "arguments",
    [["--report", "scan.json"], ["--report=scan.json"]],
)
def test_baker_preserves_caller_controlled_report_option(arguments: list[str]) -> None:
    assert _has_report_option(arguments) is True
