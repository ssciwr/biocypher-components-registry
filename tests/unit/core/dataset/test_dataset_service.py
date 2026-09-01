from __future__ import annotations

import json
from pathlib import Path

from src.core.dataset import service as dataset_service
from src.core.dataset.request import GenerationRequest, GenerationResult


# Covers post-generation distribution metadata overrides.
def test_distribution_metadata_updates_file_backed_result(tmp_path: Path) -> None:
    output_path = tmp_path / "dataset.jsonld"
    output_path.write_text(json.dumps({"@type": "sc:Dataset"}), encoding="utf-8")
    # Mock what the API eventually transfers from the metadata generator frontend create page finish step
    # This is just a dataset
    request = GenerationRequest(
        input_path="people.csv",
        output_path=str(output_path),
        content_url="https://example.org/people.csv",
        encoding_format="text/csv",
        filename="people.csv",
        sha256="abc123",
    )

    result = dataset_service._with_distribution_metadata(
        result=GenerationResult(output_path=str(output_path)), request=request
    )
    written = json.loads(output_path.read_text(encoding="utf-8"))

    assert (
        result.document["distribution"][0][
            "contentUrl"
        ]  # new in the metadata generator PR
        == "https://example.org/people.csv"
    )
    assert result.document["distribution"][0]["name"] == "people.csv"
    assert (
        written["distribution"][0]["sha256"] == "abc123"
    )  # new in the metadata generator PR


# If the user did not provide custom meta data sha/name, check that the document does not change at all (the final equality check)
def test_distribution_metadata_skips_requests_without_overrides() -> None:
    document = {"@type": "sc:Dataset", "distribution": {"name": "data.csv"}}
    result = GenerationResult(output_path="", document=document)

    updated = dataset_service._with_distribution_metadata(
        result=result,
        request=GenerationRequest(input_path="data.csv", output_path=""),
    )

    assert updated is result
    assert (
        "sha256" not in updated.document["distribution"]
    )  # not added as not specified
    assert (
        updated.document == document
    )  # document is the same, unchanged which implies the above two, but the above two are more explicit aobut what this should do.
    assert updated.document["distribution"]["name"] == "data.csv"


# Check for no document/no file case, and for existing distribution case
def test_distribution_metadata_handles_missing_and_existing_dataset_processing_paths() -> (
    None
):
    request = GenerationRequest(
        input_path="data.csv", output_path="", filename="people.csv"
    )
    missing = dataset_service._with_distribution_metadata(
        result=GenerationResult(output_path=""), request=request
    )
    dict_result = dataset_service._with_distribution_metadata(
        result=GenerationResult(
            output_path="", document={"distribution": {"@id": "file-1"}}
        ),
        request=request,
    )
    # empty distribution list (-> Create cr:FileObject) case
    list_result = dataset_service._with_distribution_metadata(
        result=GenerationResult(output_path="", document={"distribution": []}),
        request=request,
    )

    assert missing.document is None
    assert dict_result.document["distribution"]["name"] == "people.csv"
    assert list_result.document["distribution"][0]["@type"] == "cr:FileObject"


def test_distribution_metadata_ignores_blank_overrides() -> None:
    """
    Keep blank form fields from activating distribution updates.
    """
    document = {"distribution": []}
    result = GenerationResult(output_path="", document=document)

    updated = dataset_service._with_distribution_metadata(
        result=result,
        request=GenerationRequest(input_path="data.csv", output_path="", sha256=" "),
    )

    assert updated is result
    assert updated.document == document
    assert updated.document["distribution"] == []


def test_distribution_metadata_prefers_file_object_entries() -> None:
    """AI-Generated.

    Apply overrides to the matching distribution FileObject in mixed lists.
    """
    document = {
        "distribution": [
            {"@type": "cr:FileObject", "name": "other.csv"},
            {"@type": "sc:Thing"},
            {"@type": "cr:FileObject", "name": "data.csv"},
        ]
    }
    request = GenerationRequest(
        input_path="data.csv", output_path="", filename="renamed.csv"
    )

    updated = dataset_service._with_distribution_metadata(
        result=GenerationResult(output_path="", document=document), request=request
    )

    assert updated.document["distribution"][0]["name"] == "other.csv"
    assert updated.document["distribution"][1] == {"@type": "sc:Thing"}
    assert updated.document["distribution"][2]["name"] == "renamed.csv"
