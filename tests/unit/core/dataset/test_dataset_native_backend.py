from __future__ import annotations

import gzip
import json
from pathlib import Path

from src.core.dataset.backends import native as native_backend
from src.core.dataset.backends.native import NativeDatasetGenerator
from src.core.dataset.request import GenerationRequest

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
    relative = NativeDatasetGenerator()._relative_to_input(
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
    assert {"people", "scores"} == set(record_sets)
    assert record_sets["people"]["field"][0]["dataType"] == "cr:Int64"
    assert record_sets["people"]["field"][0]["@id"].startswith(
        record_sets["people"]["@id"]
    )


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


def _generate(tmp_path: Path, filename: str, content: bytes, **kwargs):
    source = tmp_path / filename
    source.write_bytes(content)
    return NativeDatasetGenerator().generate(
        GenerationRequest(
            input_path=str(source),
            output_path=str(tmp_path / "out" / "dataset.jsonld"),
            name="Example",
            description="Example dataset",
            license_value="https://creativecommons.org/licenses/by/4.0/",
            dataset_version="1.0.0",
            date_published="2024-01-01",
            url="https://example.org/data",
            **kwargs,
        )
    )


def test_native_generator_builds_file_level_metadata_for_sbgn(tmp_path: Path) -> None:
    import hashlib

    content = b"<sbgn xmlns='http://sbgn.org/libsbgn/0.3'/>"
    result = _generate(tmp_path, "map.sbgn", content)

    assert result.document is not None
    assert "recordSet" not in result.document
    (file_object,) = result.document["distribution"]
    assert file_object["@type"] == "cr:FileObject"
    assert file_object["name"] == "map.sbgn"
    assert file_object["contentSize"] == str(len(content))
    assert file_object["sha256"] == hashlib.sha256(content).hexdigest()
    assert file_object["encodingFormat"]
    assert "No supported dataset files" not in result.stderr


def test_native_generator_uses_octet_stream_for_unknown_binary(tmp_path: Path) -> None:
    result = _generate(tmp_path, "blob.zzqx9", b"\x00\x01\x02")

    assert result.document["distribution"][0]["encodingFormat"] == (
        "application/octet-stream"
    )


def test_native_generator_prefers_explicit_encoding_format(tmp_path: Path) -> None:
    result = _generate(
        tmp_path, "map.sbgn", b"<sbgn/>", encoding_format="application/xml"
    )

    assert result.document["distribution"][0]["encodingFormat"] == "application/xml"


def test_native_generator_keeps_csv_field_inference(tmp_path: Path) -> None:
    result = _generate(tmp_path, "people.csv", b"id,name\n1,Alice\n")

    assert result.document["recordSet"]
    field_names = [f["name"] for f in result.document["recordSet"][0]["field"]]
    assert field_names == ["id", "name"]


def test_native_generator_uses_filename_as_content_url_for_single_file(
    tmp_path: Path,
) -> None:
    generic = _generate(tmp_path, "glycolysis_upper.sbgn", b"<sbgn/>")
    tabular = _generate(tmp_path, "people.csv", b"id,name\n1,Alice\n")

    assert generic.document["distribution"][0]["contentUrl"] == "glycolysis_upper.sbgn"
    assert tabular.document["distribution"][0]["contentUrl"] == "people.csv"


def test_native_generator_keeps_relative_content_url_for_directory(
    tmp_path: Path,
) -> None:
    nested = tmp_path / "data" / "sub"
    nested.mkdir(parents=True)
    (nested / "map.sbgn").write_bytes(b"<sbgn/>")
    (tmp_path / "data" / "people.csv").write_text("id\n1\n", encoding="utf-8")

    result = NativeDatasetGenerator().generate(
        GenerationRequest(
            input_path=str(tmp_path / "data"),
            output_path=str(tmp_path / "out.jsonld"),
            validate=False,
        )
    )

    urls = {d["name"]: d["contentUrl"] for d in result.document["distribution"]}
    assert urls == {
        "map.sbgn": str(Path("sub") / "map.sbgn"),
        "people.csv": "people.csv",
    }
