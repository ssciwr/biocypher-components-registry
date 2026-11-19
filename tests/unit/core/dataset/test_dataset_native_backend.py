from __future__ import annotations

import ast
import gzip
import json
from pathlib import Path

import pytest

from src.core.dataset.backends import native as native_backend
from src.core.dataset.backends.native import (
    NativeDatasetBuilder,
    NativeDatasetGenerator,
)
from src.core.dataset.request import GenerationRequest
from src.core.shared.errors import InputDiscoveryError

"""
Native backend is the Python metadata generator itself that manually creates the meta data in python
By comparison, croissant-baker runs directly"""


# Covers API creator maps and helper fallbacks
def test_native_generator_maps_api_creators_and_helper_fallbacks(
    tmp_path: Path,
) -> None:
    creators = native_backend._build_creators(
        [
            {"name": "Dataset Creator", "orcid": "https://orcid.org/0000-0001"},
            {"name": "   "},
            "Legacy Creator,legacy@example.org,https://example.org",
        ]
    )
    relative = NativeDatasetBuilder()._relative_to_input(
        tmp_path.parent / "outside.csv", str(tmp_path)
    )

    assert len(creators) == 2
    assert creators[0]["identifier"] == "https://orcid.org/0000-0001"
    assert creators[1]["email"] == "legacy@example.org"
    assert relative == str(tmp_path.parent / "outside.csv")
    assert native_backend._format_date_published("not-a-date") == "not-a-date"
    # These tests check the ORCID ID and email are kept in the creator objects ready for croissant file generation


def test_native_generator_builds_dataset_from_csv_and_tsv_gz(tmp_path: Path) -> None:
    csv_path = tmp_path / "people.csv"
    csv_path.write_text("id,name\n1,Alice\n2,Bob\n", encoding="utf-8")

    tsv_gz_path = tmp_path / "scores.tsv.gz"
    with gzip.open(tsv_gz_path, "wt", encoding="utf-8") as handle:
        handle.write("score\tactive\n1.5\ttrue\n2.0\tfalse\n")

    output_path = tmp_path / "croissant.jsonld"
    request = GenerationRequest(
        input_path=str(tmp_path),
        output_path=str(output_path),
        validate=False,
        description="Test dataset",
        license_value="MIT",
        url="https://example.org/data",
        dataset_version="1.0.0",
    )

    result = NativeDatasetGenerator().generate(request)
    document = json.loads(output_path.read_text(encoding="utf-8"))

    assert result.output_path == str(output_path)
    assert "Success! Generated native Croissant metadata" in result.stdout
    assert document["@type"] == "sc:Dataset"
    assert "hasPart" not in document
    assert document["name"] == tmp_path.name
    assert len(document["distribution"]) == 2
    assert len(document["recordSet"]) == 2
    assert document["distribution"][0]["@id"] == "file_0"
    assert document["distribution"][1]["@id"] == "file_1"
    assert document["distribution"][0]["@id"] != document["recordSet"][0]["@id"]
    record_sets = {
        record_set["@id"]: record_set for record_set in document["recordSet"]
    }
    assert set(record_sets) == {"people", "scores"}
    assert record_sets["people"]["field"][0]["dataType"] == "sc:Integer"
    assert record_sets["people"]["field"][0]["@id"].startswith(
        record_sets["people"]["@id"]
    )
    compressed = next(
        item for item in document["distribution"] if item["name"] == "scores.tsv.gz"
    )
    assert compressed["encodingFormat"] == [
        "text/tab-separated-values",
        "application/gzip",
    ]


def test_native_generator_reports_default_warnings(tmp_path: Path) -> None:
    csv_path = tmp_path / "people.csv"
    csv_path.write_text("id,name\n1,Alice\n", encoding="utf-8")

    output_path = tmp_path / "croissant.jsonld"
    request = GenerationRequest(
        input_path=str(tmp_path),
        output_path=str(output_path),
    )

    result = NativeDatasetGenerator().generate(request)

    assert "Missing license; using 'UNKNOWN'." in result.stderr
    assert "Missing dataset version; using '0.1.0'." in result.stderr


def test_native_fails_instead_of_omitting_unsupported_folder_files(
    tmp_path: Path,
) -> None:
    (tmp_path / "supported.csv").write_text("id\n1\n", encoding="utf-8")
    (tmp_path / "unsupported.txt").write_text("not metadata", encoding="utf-8")
    request = GenerationRequest(
        input_path=str(tmp_path),
        output_path=str(tmp_path / "dataset.jsonld"),
        validate=False,
    )

    with pytest.raises(InputDiscoveryError, match="every selected file"):
        NativeDatasetBuilder().generate(request)

    assert not Path(request.output_path).exists()


def test_native_reachable_sources_do_not_import_croissant_baker() -> None:
    source_root = Path(native_backend.__file__).parents[1]
    sources = [source_root / "backends" / "native.py"]
    sources.extend(sorted((source_root / "formats").glob("*.py")))

    imports: list[str] = []
    for source in sources:
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)

    assert not [name for name in imports if name.startswith("croissant_baker")]
