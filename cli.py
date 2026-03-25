from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from src.core.constants import METADATA_FILENAME
from src.core.discovery import fetch_local_metadata, parse_json_metadata
from src.core.generation.cli_wizard import run_wizard
from src.core.generation.web_ui import run_server
from src.core.validator import validate


AGGREGATED_FILE = "unified_adapters_metadata.jsonld"

app = typer.Typer(
    name="biocypher-registry",
    help="BioCypher Registry — manage adapter metadata.",
    no_args_is_help=True,
)
console = Console()


def _load_metadata(path: Path) -> dict[str, Any]:
    if path.is_dir():
        _, metadata = fetch_local_metadata(path)
        return metadata

    if path.is_file():
        content = path.read_text(encoding="utf-8")
        return parse_json_metadata(content, str(path))

    raise FileNotFoundError(f"Path not found: {path}")


@app.command("generate")
def generate_cmd(
    output: str = typer.Option(
        METADATA_FILENAME,
        "--output",
        "-o",
        help="Destination path for the generated metadata file.",
    ),
) -> None:
    run_wizard(output)


@app.command("validate")
def validate_cmd(
    path: str = typer.Argument(
        ...,
        help="Path to a metadata file or to an adapter repository containing one.",
    )
) -> None:
    metadata = _load_metadata(Path(path))
    result = validate(metadata)
    if result.is_valid:
        console.print(
            f"[green]VALID[/green] (profile: {result.profile_version})"
        )
        return
    console.print(f"[red]INVALID[/red] (profile: {result.profile_version})")
    for err in result.errors:
        console.print(f"  • {err}")
    raise typer.Exit(code=1)


@app.command("web")
def web_cmd(
    host: str = typer.Option("127.0.0.1", help="Host to bind the web UI."),
    port: int = typer.Option(8000, help="Port to bind the web UI."),
    output_dir: str = typer.Option(".", help="Output directory for metadata."),
) -> None:
    console.print(f"[cyan]Serving web UI on http://{host}:{port}[/cyan]")
    run_server(host=host, port=port, output_dir=output_dir)


@app.command("list")
def list_adapters() -> None:
    if not os.path.isfile(AGGREGATED_FILE):
        console.print(
            f"Aggregated metadata file '{AGGREGATED_FILE}' not found. "
            "Please generate it first."
        )
        return

    with open(AGGREGATED_FILE, "r", encoding="utf-8") as handle:
        data = json.load(handle)
        adapters = data.get("@graph", [])

    if not adapters:
        console.print("No adapters found in the aggregated metadata.")
        return

    table = Table(title="Registered Adapters")
    table.add_column("Name", style="cyan")
    table.add_column("Version")
    for adapter in adapters:
        name = adapter.get("name", "Unknown")
        version = adapter.get("version", "Unknown")
        table.add_row(name, version)
    console.print(table)


@app.command("inspect")
def inspect_adapter(
    name: str = typer.Argument(..., help="Adapter name."),
) -> None:
    if not os.path.isfile(AGGREGATED_FILE):
        console.print(
            f"Aggregated metadata file '{AGGREGATED_FILE}' not found. "
            "Please generate it first."
        )
        return

    with open(AGGREGATED_FILE, "r", encoding="utf-8") as handle:
        data = json.load(handle)
        adapters = data.get("@graph", [])

    for adapter in adapters:
        if adapter.get("name") == name:
            console.print_json(json.dumps(adapter, indent=2))
            return

    console.print(f"[red]Adapter '{name}' not found in the registry.[/red]")


@app.command("export")
def export_metadata(
    output_file: str = typer.Argument(..., help="File path to export metadata"),
) -> None:
    if not os.path.isfile(AGGREGATED_FILE):
        console.print(
            f"Aggregated metadata file '{AGGREGATED_FILE}' not found. "
            "Please generate it first."
        )
        return

    with open(AGGREGATED_FILE, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    with open(output_file, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)

    console.print(f"[green]Exported[/green] {output_file}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
