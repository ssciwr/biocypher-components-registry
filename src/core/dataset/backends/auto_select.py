"""Dataset backend that selects another generator based on input files."""

from __future__ import annotations

from pathlib import Path

from src.core.dataset.backends.base import DatasetGenerator
from src.core.dataset.backends.croissant_baker import CroissantBakerGenerator
from src.core.dataset.backends.native import NativeDatasetGenerator
from src.core.dataset.formats.base import FormatHandler
from src.core.dataset.formats.resolver import resolve_format_handler
from src.core.dataset.request import GenerationRequest, GenerationResult
from src.core.shared.errors import UnsupportedFormatError


class AutoDatasetGenerator(DatasetGenerator):
    """Choose a concrete dataset generator before executing the request."""

    name = "auto"

    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Select a generator, run it, and prepend selection details to stdout."""
        selected_generator, reason = select_generator(request)
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


def select_generator(
    request: GenerationRequest | None = None,
) -> tuple[DatasetGenerator, str]:
    """Prefer Baker, using Native for inputs only Native can inspect."""
    if request is not None:
        files = _discover_files(request)
        handlers = _native_handlers(files)
        if handlers and any(
            not handler.croissant_baker_supported for handler in handlers
        ):
            return (
                NativeDatasetGenerator(),
                "Croissant Baker does not support every selected file.",
            )

    return (
        CroissantBakerGenerator(),
        "croissant-baker is the preferred backend when it supports the input.",
    )


def _discover_files(request: GenerationRequest) -> list[Path]:
    """Find input files using the same directory rules as Native generation."""
    input_path = Path(request.input_path).expanduser()
    if not input_path.exists():
        return []
    if input_path.is_file():
        return [input_path]
    if not input_path.is_dir():
        return []

    excluded_path = Path(request.output_path).expanduser().resolve()
    return sorted(
        path
        for path in input_path.rglob("*")
        if path.is_file() and not path.is_symlink() and path.resolve() != excluded_path
    )


def _native_handlers(files: list[Path]) -> list[FormatHandler] | None:
    """Return handlers for every file, or None when Native cannot inspect one."""
    handlers: list[FormatHandler] = []
    for path in files:
        try:
            handlers.append(resolve_format_handler(path))
        except UnsupportedFormatError:
            return None
    return handlers
