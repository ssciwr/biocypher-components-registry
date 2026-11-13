"""Dataset backend that selects another generator based on input files."""

from __future__ import annotations

from src.core.dataset.backends.base import DatasetGenerator
from src.core.dataset.backends.croissant_baker import CroissantBakerGenerator
from src.core.dataset.request import GenerationRequest, GenerationResult


class AutoDatasetGenerator(DatasetGenerator):
    """Choose a concrete dataset generator before executing the request."""

    name = "auto"

    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Select a generator, run it, and prepend selection details to stdout."""
        selected_generator, reason = select_generator()
        result = selected_generator.generate(request)

        delegate_name = getattr(
            selected_generator, "name", selected_generator.__class__.__name__
        )
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


def select_generator() -> tuple[DatasetGenerator, str]:
    """Return the primary dataset generator."""
    return (
        CroissantBakerGenerator(),
        "croissant-baker is the primary backend for supported dataset inputs.",
    )
