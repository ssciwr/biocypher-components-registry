from __future__ import annotations

from src.core.adapter.document import (
    build_adapter_creator,
    build_adapter_document,
)


def test_build_adapter_document_assembles_expected_shape() -> None:
    document = build_adapter_document(
        name="Example Adapter",
        description="Adapter description",
        version="1.0.0",
        license_value="MIT",
        code_repository="https://example.org/repo",
        creators=[
            build_adapter_creator(
                name="Edwin Carreno",
                affiliation="SSC",
                identifier="https://orcid.org/0000-0000-0000-0000",
            )
        ],
        keywords=["adapter", "biocypher"],
        datasets=[{"@type": "sc:Dataset", "name": "Example dataset"}],
    )

    assert document["@type"] == "SoftwareSourceCode"
    assert document["@id"] == "example-adapter"
    assert document["creator"][0]["name"] == "Edwin Carreno"
    assert document["keywords"] == ["adapter", "biocypher"]
    assert document["hasPart"][0]["name"] == "Example dataset"
