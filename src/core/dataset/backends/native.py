"""Independent native dataset backend and its private in-process builder."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.core.dataset.backends.base import DatasetGenerator
from src.core.dataset.document import (
    build_creator,
    build_dataset_document,
    build_distribution_file,
    build_field,
    build_record_set,
)
from src.core.dataset.formats.resolver import resolve_format_handler
from src.core.dataset.request import FileInspection, GenerationRequest, GenerationResult
from src.core.shared.creators import parse_dataset_creator_string
from src.core.shared.errors import InputDiscoveryError, UnsupportedFormatError
from src.core.shared.licenses import normalize_license_url
from src.core.validation.dataset import validate_dataset


class NativeDatasetGenerator(DatasetGenerator):
    """Invoke native generation through the common bounded process boundary."""

    name = "native"

    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Generate metadata without running native parsing in the caller process."""
        from src.core.dataset.native_process import generate_native_in_bounded_process

        return generate_native_in_bounded_process(request)


class NativeDatasetBuilder:
    """Build native metadata in-process only inside the private worker."""

    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Inspect input files, build a dataset document, and optionally validate it."""
        input_path = Path(request.input_path).expanduser()
        files = self._discover_files(
            input_path,
            excluded_path=Path(request.output_path).expanduser(),
        )
        warnings: list[str] = []
        inspections: list[FileInspection] = []
        unsupported: list[str] = []

        for path in files:
            try:
                handler = resolve_format_handler(path)
                inspections.append(handler.inspect(path))
            except UnsupportedFormatError as exc:
                unsupported.append(str(exc))

        if unsupported:
            details = "; ".join(unsupported)
            raise InputDiscoveryError(
                "Native generation requires every selected file to be supported: "
                f"{details}"
            )

        if not inspections:
            raise InputDiscoveryError(
                "No supported dataset files were found in the input path."
            )

        document = self._build_document(request, inspections, warnings)
        output_path = Path(request.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(document, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        stdout_lines = [
            "Success! Generated native Croissant metadata",
            f"Files: {len(inspections)}",
            f"Record sets: {len(inspections)}",
            f"Saved to: {output_path}",
        ]
        stderr_lines = list(warnings)
        if request.validate:
            validation_result = validate_dataset(document)
            if validation_result.is_valid:
                stdout_lines.insert(0, "Validation completed!")
            else:
                stderr_lines.append(
                    "Validation warnings: " + "; ".join(validation_result.errors)
                )

        return GenerationResult(
            output_path=str(output_path),
            stdout="\n".join(stdout_lines),
            stderr="\n".join(stderr_lines),
            document=document,
            warnings=warnings,
        )

    def _discover_files(
        self, input_path: Path, *, excluded_path: Path | None = None
    ) -> list[Path]:
        """Resolve the files that should be inspected for one input path."""
        if not input_path.exists():
            raise InputDiscoveryError(f"Input path does not exist: {input_path}")
        if input_path.is_file():
            return [input_path]
        files = sorted(
            path
            for path in input_path.rglob("*")
            if path.is_file()
            and not path.is_symlink()
            and (excluded_path is None or path.resolve() != excluded_path.resolve())
        )
        if not files:
            raise InputDiscoveryError(f"No files were found under: {input_path}")
        return files

    def _build_document(
        self,
        request: GenerationRequest,
        inspections: list[FileInspection],
        warnings: list[str],
    ) -> dict:
        """Build a dataset document from normalized file inspections."""
        dataset_name = request.name or Path(request.input_path).expanduser().name
        if not request.name:
            warnings.append(f"Missing dataset name; using '{dataset_name}'.")

        description = request.description or "Generated from local dataset files."
        if not request.description:
            warnings.append("Missing description; using generated default.")

        version = request.dataset_version or "0.1.0"
        if not request.dataset_version:
            warnings.append("Missing dataset version; using '0.1.0'.")

        license_value = normalize_license_url(request.license_value or "UNKNOWN")
        if not request.license_value:
            warnings.append("Missing license; using 'UNKNOWN'.")

        url = request.url or Path(request.input_path).expanduser().resolve().as_uri()
        if not request.url:
            warnings.append("Missing URL; using a file:// URI for the input path.")

        creators = _build_creators(request.creators)
        raw_date_published = request.date_published or _infer_date_published(
            inspections
        )
        date_published = _format_date_published(raw_date_published)
        if not request.date_published:
            warnings.append(f"Missing date published; using '{date_published}'.")
        distributions = []
        record_sets = []
        for index, inspection in enumerate(inspections):
            relative = self._relative_to_input(inspection.path, request.input_path)
            file_id = f"file_{index}"
            record_name = _record_name(inspection.path.name)
            record_set_id = _sanitize_id(record_name)
            file_size = str(inspection.path.stat().st_size)
            sha256 = _compute_file_hash(inspection.path)
            distributions.append(
                build_distribution_file(
                    content_url=relative,
                    encoding_format=inspection.encoding_format,
                    name=inspection.path.name,
                    file_id=file_id,
                    content_size=file_size,
                    sha256=sha256,
                )
            )
            fields = [
                build_field(
                    name=field.name,
                    data_type=field.data_type,
                    description_suffix=inspection.path.name,
                    record_set_id=record_set_id,
                    file_object_id=file_id,
                )
                for field in inspection.fields
            ]
            record_sets.append(
                build_record_set(
                    name=record_name,
                    fields=fields,
                    record_set_id=record_set_id,
                    description=f"Records from {inspection.path.name}",
                )
            )

        return build_dataset_document(
            name=dataset_name,
            description=description,
            version=version,
            license_value=license_value,
            url=url,
            date_published=date_published,
            citation=request.citation or "",
            creators=creators,
            distributions=distributions,
            record_sets=record_sets,
        )

    def _relative_to_input(self, path: Path, input_path: str) -> str:
        """Return a path relative to the input root when possible."""
        input_root = Path(input_path).expanduser()
        try:
            return str(path.relative_to(input_root))
        except ValueError:
            return str(path)


def _record_name(filename: str) -> str:
    """Preserve record IDs while handling a compression suffix explicitly."""
    path = Path(filename)
    if path.suffix.lower() in {".bz2", ".gz", ".xz"}:
        path = Path(path.stem)
    return path.stem


def _sanitize_id(value: str) -> str:
    """Build a stable Croissant identifier without Baker implementation imports."""
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("_")
    return normalized or "records"


def _compute_file_hash(path: Path) -> str:
    """Hash a native input independently from Croissant Baker internals."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_creators(raw_creators: list[str | dict[str, Any]]) -> list[dict]:
    """Build dataset creator objects from API JSON or legacy strings."""
    creators = []
    for raw in raw_creators:
        if isinstance(raw, dict):
            creator = _build_creator_from_mapping(raw)
            if creator:
                creators.append(creator)
            continue

        spec = parse_dataset_creator_string(raw)
        if spec and spec.name:
            creators.append(
                build_creator(
                    name=spec.name,
                    email=spec.email,
                    url=spec.url,
                    affiliation=spec.affiliation,
                    identifier=spec.identifier,
                    creator_type=spec.creator_type,
                )
            )
    return creators


# Keeps  API JSON creator support separate from legacy string parsing which CLI/others still use (for creators input)
# In turn this makes the frontend much cleaner/more typed.
def _build_creator_from_mapping(raw: dict[str, Any]) -> dict[str, Any] | None:
    name = str(raw.get("name") or "").strip()
    if not name:
        return None

    identifier = (
        str(raw.get("identifier") or "").strip() or str(raw.get("orcid") or "").strip()
    )
    return build_creator(
        name=name,
        email=str(raw.get("email") or "").strip(),
        url=str(raw.get("url") or "").strip(),
        affiliation=str(raw.get("affiliation") or "").strip(),
        identifier=identifier,
        creator_type=str(raw.get("creator_type") or "Person").strip(),
    )


def _infer_date_published(inspections: list[FileInspection]) -> str:
    """Infer a publication date from the newest inspected source file."""
    latest_mtime = max(inspection.path.stat().st_mtime for inspection in inspections)
    return _format_date_published(
        datetime.fromtimestamp(latest_mtime, tz=UTC).date().isoformat()
    )


def _format_date_published(value: str) -> str:
    """Normalize a date or datetime string into ISO format when possible."""
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value
    if "T" not in value:
        return parsed.isoformat()
    return parsed.isoformat()
