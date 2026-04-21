"""Dataset backend that shells out to the external ``croissant-baker`` CLI."""

from __future__ import annotations

import subprocess

from src.core.dataset.backends.base import DatasetGenerator
from src.core.dataset.request import GenerationRequest, GenerationResult
from src.core.shared.errors import GeneratorError


class CroissantBakerGenerator(DatasetGenerator):
    """Delegate dataset generation to the installed ``croissant-baker`` tool."""

    name = "croissant-baker"

    def __init__(self, executable: str = "croissant-baker") -> None:
        """Store the executable name used for backend invocation."""
        self.executable = executable

    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Run ``croissant-baker`` and return its process output."""
        command = build_croissant_baker_command(
            request=request,
            executable=self.executable,
        )
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise GeneratorError(
                "Could not find the 'croissant-baker' executable. "
                "Install it or select another generator."
            ) from exc

        if result.returncode != 0:
            details = result.stderr.strip() or result.stdout.strip() or "No output."
            raise GeneratorError(
                f"croissant-baker failed with exit code {result.returncode}: {details}"
            )

        return GenerationResult(
            output_path=request.output_path,
            stdout=result.stdout,
            stderr=result.stderr,
        )


def build_croissant_baker_command(
    request: GenerationRequest,
    executable: str = "croissant-baker",
) -> list[str]:
    """Translate a dataset request into ``croissant-baker`` CLI arguments."""
    command = [executable, "--input", request.input_path, "--output", request.output_path]

    if request.validate:
        command.append("--validate")

    option_pairs = [
        ("--name", request.name),
        ("--description", request.description),
        ("--url", request.url),
        ("--license", request.license_value),
        ("--citation", request.citation),
        ("--dataset-version", request.dataset_version),
        ("--date-published", request.date_published),
    ]
    for flag, value in option_pairs:
        if value:
            command.extend([flag, value])

    for creator in request.creators:
        if creator:
            command.extend(["--creator", creator])

    command.extend(request.extra_args)
    return command
