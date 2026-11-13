"""Dataset backend that shells out to the external ``croissant-baker`` CLI."""

from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Any

from src.core.dataset.backends.base import DatasetGenerator
from src.core.dataset.process import run_bounded_process
from src.core.dataset.request import GenerationRequest, GenerationResult
from src.core.dataset.upload.limits import MAX_GENERATED_JSON_BYTES
from src.core.shared.creators import parse_dataset_creator_string
from src.core.shared.errors import GeneratorError


class CroissantBakerGenerator(DatasetGenerator):
    """Delegate dataset generation to the installed ``croissant-baker`` tool."""

    name = "croissant-baker"

    def __init__(self, executable: str = "croissant-baker") -> None:
        """Store the executable name used for backend invocation."""
        self.executable = executable

    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Run ``croissant-baker`` and return its process output."""
        scratch = Path(request.output_path).parent
        manages_report = not _has_report_option(request.extra_args)
        report_path = (
            scratch / f".baker-report-{secrets.token_hex(6)}.json"
            if manages_report
            else None
        )
        command = build_croissant_baker_command(
            request=request,
            executable=self.executable,
        )
        if report_path is not None:
            command.extend(["--report", str(report_path)])
        try:
            try:
                result = run_bounded_process(command, scratch_directory=scratch)
            except FileNotFoundError as exc:
                raise GeneratorError(
                    "Could not find the 'croissant-baker' executable. "
                    "Install it or select another generator."
                ) from exc

            if result.timed_out:
                raise GeneratorError(
                    "croissant-baker exceeded the generation time limit."
                )
            if result.returncode != 0:
                details = result.stderr.strip() or result.stdout.strip() or "No output."
                raise GeneratorError(
                    f"croissant-baker failed with exit code {result.returncode}: {details}"
                )
            warnings = _read_scan_warnings(report_path) if report_path else []
        except GeneratorError:
            Path(request.output_path).unlink(missing_ok=True)
            raise
        finally:
            if report_path is not None:
                report_path.unlink(missing_ok=True)

        return GenerationResult(
            output_path=request.output_path,
            stdout=result.stdout,
            stderr=result.stderr,
            warnings=warnings,
        )


def build_croissant_baker_command(
    request: GenerationRequest,
    executable: str = "croissant-baker",
) -> list[str]:
    """Translate a dataset request into ``croissant-baker`` CLI arguments."""
    command = [
        executable,
        "--input",
        request.input_path,
        "--output",
        request.output_path,
    ]

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
        command.extend(_creator_args(creator))

    command.extend(request.extra_args)
    return command


def _has_report_option(arguments: list[str]) -> bool:
    """Return whether the caller explicitly controls Baker's report output."""
    return any(
        argument == "--report" or argument.startswith("--report=")
        for argument in arguments
    )


def _read_scan_warnings(report_path: Path) -> list[str]:
    """Translate Baker scan outcomes into bounded warnings without redefining success."""
    try:
        if report_path.stat().st_size > MAX_GENERATED_JSON_BYTES:
            return ["Croissant Baker scan details exceeded the application size limit."]
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ["Croissant Baker completed without a readable scan report."]
    except (OSError, json.JSONDecodeError):
        return ["Croissant Baker completed with an unreadable scan report."]

    files = report.get("files")
    if not isinstance(files, list):
        return ["Croissant Baker completed with an invalid scan report."]
    if not files:
        return ["Croissant Baker did not report any discovered dataset files."]
    omitted, diagnostics = _scan_finding_counts(files)
    warnings: list[str] = []
    if omitted:
        warnings.append(
            f"Croissant Baker did not describe {omitted} discovered file(s)."
        )
    if diagnostics:
        warnings.append(
            f"Croissant Baker reported {diagnostics} non-fatal diagnostic(s)."
        )
    return warnings


def _scan_finding_counts(files: list[Any]) -> tuple[int, int]:
    """Count omitted files and non-fatal diagnostics in a Baker report."""
    accepted = {"described", "linked", "referenced"}
    omitted = sum(
        not isinstance(entry, dict) or entry.get("outcome") not in accepted
        for entry in files
    )
    diagnostics = sum(_diagnostic_count(entry) for entry in files)
    return omitted, diagnostics


def _diagnostic_count(entry: Any) -> int:
    """Return the number of diagnostics attached to one report entry."""
    if not isinstance(entry, dict):
        return 0
    diagnostics = entry.get("diagnostics", [])
    if isinstance(diagnostics, list):
        return len(diagnostics)
    return int(bool(diagnostics))


# Keeps branch-added structured creator support out of the original command loop.
# Splitting into two functions keeps build_croissant_baker_command under the Sonar limit while
# isolating the new API JSON creator path, e.g. mapping a {name, email,
# identifier} creator into the pipe-delimited CLI value, from the pre-existing
# string creator path. It's the mapping that increased it.
def _creator_args(creator: str | dict[str, Any]) -> list[str]:
    if isinstance(creator, dict):
        name = str(creator.get("name") or "").strip()
        email = str(creator.get("email") or "").strip()
        url = str(creator.get("url") or "").strip()
    else:
        spec = parse_dataset_creator_string(creator)
        if spec is None:
            return []
        name, email, url = spec.name, spec.email, spec.url

    if not name:
        return []

    value = f"{name},{email},{url}".rstrip(",")
    return ["--creator", value]
