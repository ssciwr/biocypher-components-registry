"""Dataset backend that selects another generator based on input files."""

from __future__ import annotations

from pathlib import Path

from croissant_baker.files import discover_files as discover_baker_files

from src.core.dataset.backends.base import DatasetGenerator
from src.core.dataset.backends.croissant_baker import CroissantBakerGenerator
from src.core.dataset.backends.native import NativeDatasetGenerator
from src.core.dataset.request import GenerationRequest, GenerationResult
from src.core.shared.errors import InputDiscoveryError


class AutoDatasetGenerator(DatasetGenerator):
    """Choose a concrete dataset generator before executing the request."""

    name = "auto"

    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Select a generator, run it, and prepend selection details to stdout."""
        selected_generator, reason = select_generator_for_request(request)
        result = selected_generator.generate(request)

        delegate_name = getattr(selected_generator, "name", selected_generator.__class__.__name__)
        selection_lines = [
            f"Auto-selected generator: {delegate_name}",
            f"Reason: {reason}",
        ]

        stdout_parts = ["\n".join(selection_lines)]
        if result.stdout.strip():
            stdout_parts.append(result.stdout.strip())

        return GenerationResult(
            output_path=result.output_path,
            stdout="\n".join(stdout_parts),
            stderr=result.stderr,
            document=result.document,
            warnings=result.warnings,
        )


def select_generator_for_request(
    request: GenerationRequest,
) -> tuple[DatasetGenerator, str]:
    """Pick the most suitable dataset generator for the given request."""
    files = _discover_input_files(Path(request.input_path).expanduser())

    for path in files:
        suffixes = tuple(s.lower() for s in path.suffixes)
        if suffixes[-2:] == (".tsv", ".gz"):
            return (
                NativeDatasetGenerator(),
                f"detected '{path.name}', which is outside croissant-baker's supported path.",
            )

    return (
        CroissantBakerGenerator(),
        "detected only standard dataset inputs handled by croissant-baker.",
    )


def _discover_input_files(input_path: Path) -> list[Path]:
    """Expand a request input path into the files considered for selection."""
    if not input_path.exists():
        raise InputDiscoveryError(f"Input path does not exist: {input_path}")
    if input_path.is_file():
        return [input_path]

    relative_paths = discover_baker_files(str(input_path))
    files = [input_path / relative_path for relative_path in relative_paths]
    if not files:
        raise InputDiscoveryError(f"No files were found under: {input_path}")
    return files
