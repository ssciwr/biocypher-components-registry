from __future__ import annotations

import json

import pytest

from src.core.dataset.backends import list_generators, resolve_generator
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
from src.core.dataset.request import GenerationRequest
from src.core.shared.errors import UnsupportedGeneratorError


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


def test_auto_selects_croissant_baker_as_the_primary_backend() -> None:
    generator, reason = select_generator()

    assert isinstance(generator, CroissantBakerGenerator)
    assert "primary backend" in reason


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
