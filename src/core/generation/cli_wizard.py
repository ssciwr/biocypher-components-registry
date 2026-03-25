"""Guided CLI wizard for croissant.jsonld generation.

Walks the user through three sections:
  1. Adapter information
  2. Creators / developers
  3. Datasets
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer
from rich.console import Console
from rich.panel import Panel

from src.core.generation.builder import (
    build_adapter,
    build_creator,
    build_dataset,
    build_distribution_file,
    build_field,
    build_record_set,
)
from src.core.generation.inference import infer_fields_from_file
from src.core.validator import validate

console = Console()

_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+")


def _collect_adapter_info() -> dict[str, Any]:
    console.print(Panel("[bold]Section 1 / 3 — Adapter information[/bold]"))

    name = typer.prompt("  Adapter name [required]")
    description = typer.prompt("  Description [required]")
    version = _prompt_semver("  Version [required]", default="0.1.0")
    license_url = typer.prompt(
        "  License (URL or SPDX identifier, e.g. MIT or "
        "https://opensource.org/licenses/MIT) [required]"
    )
    code_repository = typer.prompt("  Code repository URL [required]")
    keywords = _prompt_required_keywords(
        "  Keywords (comma-separated, e.g. proteomics,ontology,uniprot) [required]"
    )

    return {
        "name": name,
        "description": description,
        "version": version,
        "license_url": license_url,
        "code_repository": code_repository,
        "keywords": keywords,
    }


def _collect_creators() -> list[dict[str, Any]]:
    console.print(Panel("[bold]Section 2 / 3 — Creators / developers[/bold]"))
    console.print("  At least one creator is required.\n")

    creators = []
    while True:
        index = len(creators) + 1
        console.print(f"  [cyan]Creator #{index}[/cyan]")
        dev_name = typer.prompt("    Full name [required]")
        affiliation = typer.prompt("    Affiliation [optional]", default="")
        orcid = typer.prompt(
            "    ORCID (e.g. https://orcid.org/0000-...) [optional]",
            default="",
        )
        creators.append(build_creator(dev_name, affiliation, orcid))

        if not typer.confirm("\n  Add another creator?", default=False):
            break
        console.print()

    return creators


def _collect_datasets() -> list[dict[str, Any]]:
    console.print(Panel("[bold]Section 3 / 3 — Datasets[/bold]"))
    console.print(
        "  Enter details for each dataset this adapter integrates.\n"
        "  At least one dataset is required.\n"
    )

    datasets = []
    while True:
        index = len(datasets) + 1
        console.print(f"  [cyan]Dataset #{index} — basic metadata[/cyan]")

        ds_name = typer.prompt("    Name [required]")
        ds_description = typer.prompt("    Description [required]")
        ds_version = _prompt_semver("    Version [required]", default="")
        ds_license = typer.prompt("    License (URL or SPDX identifier) [required]")
        ds_url = typer.prompt("    Dataset URL [required]")
        ds_date = _prompt_recommended(
            "    Date published (YYYY-MM-DD) [recommended]",
            guidance=(
                "mlcroissant recommends datePublished; "
                "empty values produce warnings."
            ),
        )
        ds_cite = _prompt_recommended(
            "    Citation DOI or string [recommended]",
            guidance=(
                "mlcroissant recommends citeAs; "
                "empty values produce warnings."
            ),
        )

        distribution: List[Dict[str, Any]] = []
        if typer.confirm(
            "\n    Add distribution file(s) for this dataset?", default=False
        ):
            distribution = _collect_distribution_files(ds_name)

        record_sets: List[Dict[str, Any]] = []
        if distribution and typer.confirm(
            "\n    Define fields / schema for this dataset?", default=False
        ):
            rs = _collect_record_set(ds_name, distribution)
            if rs is not None:
                record_sets.append(rs)

        datasets.append(
            build_dataset(
                name=ds_name,
                description=ds_description,
                version=ds_version,
                license_url=ds_license,
                url=ds_url,
                date_published=ds_date,
                cite_as=ds_cite,
                distribution=distribution or None,
                record_set=record_sets or None,
            )
        )

        if not typer.confirm("\n  Add another dataset?", default=False):
            break
        console.print()

    return datasets


def _prompt_semver(message: str, default: str = "") -> str:
    while True:
        value = typer.prompt(message, default=default)
        if not value:
            console.print(
                "    [yellow]Version cannot be empty. "
                "Please enter a version string (e.g. 1.0.0).[/yellow]"
            )
            continue
        if not _SEMVER_RE.match(value):
            console.print(
                f"    [yellow]Note: '{value}' does not follow "
                "MAJOR.MINOR.PATCH. mlcroissant may warn about this.[/yellow]"
            )
        return value


def _collect_distribution_files(dataset_name: str) -> List[Dict[str, Any]]:
    console.print(
        f"\n    [cyan]Distribution files for '{dataset_name}'[/cyan]"
    )
    files: List[Dict[str, Any]] = []
    while True:
        idx = len(files) + 1
        console.print(f"      File #{idx}")
        content_url = typer.prompt("        Content URL or relative path [required]")
        encoding_format = typer.prompt(
            "        Encoding format (e.g. text/csv, text/tab-separated-values) [required]",
            default="text/csv",
        )
        file_name = typer.prompt(
            "        File name (optional; inferred from URL if empty) [optional]",
            default="",
        )
        md5, sha256 = _prompt_checksums()
        files.append(
            build_distribution_file(
                content_url=content_url,
                encoding_format=encoding_format,
                name=file_name,
                md5=md5,
                sha256=sha256,
            )
        )
        if not typer.confirm("      Add another file?", default=False):
            break

    return files


def _collect_record_set(
    dataset_name: str,
    distribution_files: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    rs_name = typer.prompt(
        "\n      Record set name", default=f"{dataset_name} records"
    )
    rs_id = typer.prompt(
        "      Record set @id (slug)", default=_to_id(rs_name)
    )
    source_file = distribution_files[0] if distribution_files else None
    file_object_id = source_file["@id"] if source_file else ""

    infer = typer.confirm(
        "      Infer fields from a local data file?", default=False
    )

    fields: List[Dict[str, Any]] = []
    if infer:
        fields, cancel_file = _infer_fields(rs_id, file_object_id)
        if cancel_file and source_file is not None:
            distribution_files.remove(source_file)
            console.print(
                "      [yellow]Cancelled the selected file entry.[/yellow]"
            )
            return None
    else:
        fields = _collect_fields_manually(rs_id, file_object_id)

    if not fields:
        console.print("      [yellow]No fields defined — RecordSet skipped.[/yellow]")
        return None

    return build_record_set(name=rs_name, fields=fields, record_set_id=rs_id)


def _infer_fields(
    record_set_id: str, file_object_id: str
) -> tuple[List[Dict[str, Any]], bool]:
    while True:
        local_path = typer.prompt("        Local file path (CSV or TSV) [required]")
        try:
            fields, detected_format = infer_fields_from_file(
                local_path, record_set_id, file_object_id
            )
            console.print(
                f"        [green]✓ Inferred {len(fields)} field(s) "
                f"from {local_path} ({detected_format})[/green]"
            )
            return fields, False
        except Exception as exc:  # noqa: BLE001
            console.print(f"        [red]Inference failed:[/red] {exc}")
            if typer.confirm(
                "        Cancel this file entry?", default=True
            ):
                return [], True
            if not typer.confirm(
                "        Retry with another local file path?", default=False
            ):
                return [], False


def _collect_fields_manually(
    record_set_id: str, file_object_id: str
) -> List[Dict[str, Any]]:
    console.print("        Enter fields one at a time:")
    fields: List[Dict[str, Any]] = []
    while True:
        idx = len(fields) + 1
        console.print(f"        [cyan]Field #{idx}[/cyan]")
        f_name = typer.prompt("          Column name [required]")
        f_desc = typer.prompt("          Description [optional]", default="")
        f_type = typer.prompt(
            "          Data type [required]",
            default="sc:Text",
            show_choices=True,
            prompt_suffix=(
                " (sc:Text / sc:Integer / sc:Float / sc:Boolean): "
            ),
        )
        f_example_raw = typer.prompt(
            "          Example value [optional]", default=""
        )
        examples = [f_example_raw] if f_example_raw else []
        fields.append(
            build_field(
                name=f_name,
                description=f_desc,
                data_type=f_type,
                examples=examples,
                record_set_id=record_set_id,
                file_object_id=file_object_id,
            )
        )
        if not typer.confirm("        Add another field?", default=False):
            break
    return fields


def _to_id(text: str) -> str:
    return text.lower().replace(" ", "-").replace("_", "-")


def _prompt_recommended(label: str, guidance: str) -> str:
    while True:
        value = typer.prompt(label, default="")
        if value:
            return value
        console.print(f"    [yellow]{guidance}[/yellow]")
        if typer.confirm(
            "    Skip this recommended field anyway?", default=False
        ):
            return ""


def _prompt_required_keywords(label: str) -> list[str]:
    while True:
        raw = typer.prompt(label)
        keywords = [k.strip() for k in raw.split(",") if k.strip()]
        if keywords:
            return keywords
        console.print("  [red]At least one keyword is required.[/red]")


def _prompt_checksums() -> tuple[str, str]:
    while True:
        md5 = typer.prompt("        MD5 checksum [optional]", default="")
        sha256 = typer.prompt("        SHA-256 checksum [optional]", default="")
        if md5 or sha256:
            return md5, sha256
        console.print(
            "        [yellow]mlcroissant requires at least one checksum "
            "(md5 or sha256) per distribution file.[/yellow]"
        )


def run_wizard(output_path: str = "croissant.jsonld") -> None:
    console.print(
        "\n[bold cyan]BioCypher Adapter Metadata Generator[/bold cyan]\n"
        "This wizard will guide you through the required fields.\n"
    )

    adapter_info = _collect_adapter_info()
    console.print()
    creators = _collect_creators()
    console.print()
    datasets = _collect_datasets()

    doc = build_adapter(
        name=adapter_info["name"],
        description=adapter_info["description"],
        version=adapter_info["version"],
        license_url=adapter_info["license_url"],
        code_repository=adapter_info["code_repository"],
        creators=creators,
        keywords=adapter_info["keywords"],
        datasets=datasets,
    )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)

    console.print(f"\n[green]✓ Saved:[/green] {out}")

    result = validate(doc)
    if result.is_valid:
        console.print(
            f"[green]✓ Validation passed[/green] "
            f"(profile: {result.profile_version})"
        )
    else:
        console.print(
            f"\n[yellow]⚠ Validation warnings[/yellow] "
            f"(profile: {result.profile_version}) — "
            "please correct before registering:"
        )
        for err in result.errors:
            console.print(f"  • {err}")
