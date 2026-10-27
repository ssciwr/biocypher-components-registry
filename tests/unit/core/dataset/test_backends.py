from __future__ import annotations

import pytest

from src.core.dataset.backends import list_generators, resolve_generator
from src.core.dataset.backends.auto_select import (
    AutoDatasetGenerator,
    select_generator_for_request,
)
from src.core.dataset.backends.croissant_baker import CroissantBakerGenerator
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


def test_auto_selects_croissant_baker_for_standard_csv_input(tmp_path) -> None:
    dataset_path = tmp_path / "data.csv"
    dataset_path.write_text("id\n1\n", encoding="utf-8")

    generator, reason = select_generator_for_request(
        GenerationRequest(input_path=str(dataset_path), output_path="out.jsonld")
    )

    assert isinstance(generator, CroissantBakerGenerator)
    assert "standard dataset inputs" in reason


def test_auto_selects_native_for_tsv_gz_input(tmp_path) -> None:
    dataset_path = tmp_path / "data.tsv.gz"
    dataset_path.write_bytes(b"dummy")

    generator, reason = select_generator_for_request(
        GenerationRequest(input_path=str(dataset_path), output_path="out.jsonld")
    )

    assert isinstance(generator, NativeDatasetGenerator)
    assert ".tsv.gz" in reason


def test_auto_selects_native_for_file_without_structured_handler(tmp_path) -> None:
    dataset_path = tmp_path / "map.sbgn"
    dataset_path.write_text("<sbgn/>", encoding="utf-8")

    generator, _ = select_generator_for_request(
        GenerationRequest(input_path=str(dataset_path), output_path="out.jsonld")
    )

    assert isinstance(generator, NativeDatasetGenerator)


def test_auto_keeps_croissant_baker_for_baker_only_formats(tmp_path) -> None:
    """Formats croissant-baker handles but native does not must not be downgraded."""
    (tmp_path / "scan.png").write_bytes(b"not-really-a-png")

    generator, _ = select_generator_for_request(
        GenerationRequest(input_path=str(tmp_path), output_path="out.jsonld")
    )

    assert isinstance(generator, CroissantBakerGenerator)


def test_auto_keeps_croissant_baker_for_mixed_directory(tmp_path) -> None:
    (tmp_path / "data.csv").write_text("id\n1\n", encoding="utf-8")
    (tmp_path / "notes.sbgn").write_text("<sbgn/>", encoding="utf-8")

    generator, _ = select_generator_for_request(
        GenerationRequest(input_path=str(tmp_path), output_path="out.jsonld")
    )

    assert isinstance(generator, CroissantBakerGenerator)


def test_auto_selects_native_for_json_which_baker_does_not_handle(tmp_path) -> None:
    dataset_path = tmp_path / "records.jsonl"
    dataset_path.write_text('{"a": 1}\n', encoding="utf-8")

    generator, _ = select_generator_for_request(
        GenerationRequest(input_path=str(dataset_path), output_path="out.jsonld")
    )

    assert isinstance(generator, NativeDatasetGenerator)
