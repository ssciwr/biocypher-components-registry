from src.core.registration.service import _build_uniqueness_key


def test_build_uniqueness_key_prefers_metadata_adapter_id_over_submitted_name() -> None:
    """Use the metadata adapter id as the canonical uniqueness key source."""
    uniqueness_key = _build_uniqueness_key(
        {
            "@id": "example-adapter",
            "name": "Example Adapter",
            "version": "1.0.0",
        },
        fallback_adapter_id="example-adapter-duplicate",
    )

    assert uniqueness_key == "example-adapter::1.0.0"


def test_build_uniqueness_key_changes_when_version_changes() -> None:
    first = _build_uniqueness_key({"@id": "example-adapter", "version": "1.0.0"})
    second = _build_uniqueness_key({"@id": "example-adapter", "version": "1.0.1"})
    assert first != second
    assert first == "example-adapter::1.0.0"
    assert second == "example-adapter::1.0.1"
