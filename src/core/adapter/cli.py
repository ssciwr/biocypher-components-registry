"""Interactive and scripted CLI commands for adapter metadata generation."""

from __future__ import annotations

import re
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from src.core.adapter.config import request_from_config as adapter_request_from_config
from src.core.adapter.request import AdapterGenerationRequest
from src.core.adapter.service import execute_request as execute_adapter_request
from src.core.dataset.config import request_from_config as dataset_request_from_config
from src.core.dataset.request import GenerationRequest
from src.core.dataset.service import (
    ensure_supported_generator as ensure_supported_dataset_backend,
)
from src.core.shared.ids import slugify_identifier


console = Console()
_ADAPTER_GENERATOR = "native"
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+")
app = typer.Typer(
    help="Generate adapter Croissant metadata.",
    no_args_is_help=True,
)

_DATASET_FLAG_MAP = {
    "--input": "input_path",
    "--dataset-input": "input_path",
    "--name": "name",
    "--dataset-name": "name",
    "--description": "description",
    "--dataset-description": "description",
    "--url": "url",
    "--dataset-url": "url",
    "--license": "license_value",
    "--dataset-license": "license_value",
    "--citation": "citation",
    "--dataset-citation": "citation",
    "--dataset-version": "dataset_version",
    "--date-published": "date_published",
    "--dataset-date-published": "date_published",
    "--creator": "creators",
    "--dataset-creator": "creators",
}


def _print_completion_banner(
    request: AdapterGenerationRequest,
    stdout: str,
    stderr: str,
) -> None:
    """Render the final success banner and generation report."""
    body = Text()
    body.append("Status\n", style="bold green")
    body.append("Generation completed successfully\n\n", style="white")
    body.append("Output\n", style="bold")
    body.append(f"{request.output_path}", style="white")
    console.print(
        Panel(
            body,
            title="Adapter Ready",
            border_style="green",
            expand=False,
        )
    )
    report_parts: list[str] = []
    if stdout.strip():
        report_parts.append(stdout.strip())
    if stderr.strip():
        report_parts.append(stderr.strip())
    if report_parts:
        console.print(
            Panel(
                Text("\n\n".join(report_parts), style="white"),
                title="Generation Report",
                border_style="cyan",
                expand=False,
            )
        )


def _run_request(request: AdapterGenerationRequest, generator: str) -> None:
    """Execute one adapter request and exit cleanly on backend errors."""
    try:
        result = execute_adapter_request(request=request, generator=generator)
    except (RuntimeError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    _print_completion_banner(
        request=request,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def _run_request_with_recovery(request: AdapterGenerationRequest, generator: str) -> None:
    """Execute a guided request and allow iterative fixes after failures."""
    while True:
        try:
            result = execute_adapter_request(request=request, generator=generator)
        except (RuntimeError, ValueError) as exc:
            console.print(f"[red]{exc}[/red]")
            if not typer.confirm("Continue editing the adapter input data?", default=True):
                raise typer.Exit(code=1) from exc
            review_adapter_request(request)
            continue

        _print_completion_banner(
            request=request,
            stdout=result.stdout,
            stderr=result.stderr,
        )
        return


@app.command(
    "direct",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    help=(
        "Direct mode: generate adapter Croissant metadata from explicit adapter "
        "fields plus one or more existing dataset Croissant files or inline "
        "generated dataset blocks."
    ),
)
def direct_cmd(
    ctx: typer.Context,
    dataset_generator: str = typer.Option(
        "croissant-baker",
        "--dataset-generator",
        help="Dataset generator backend used for all generated datasets in this adapter.",
    ),
    output: str = typer.Option(
        "croissant_adapter.jsonld",
        "--output",
        "-o",
        help="Destination JSON-LD file.",
    ),
    validate: bool = typer.Option(
        True,
        "--validate/--no-validate",
        help="Validate the generated adapter metadata.",
    ),
    name: str = typer.Option(..., "--name", help="Adapter name."),
    description: str = typer.Option(..., "--description", help="Adapter description."),
    version: str = typer.Option(..., "--version", help="Adapter version."),
    license_value: str = typer.Option(..., "--license", help="Adapter license."),
    code_repository: str = typer.Option(
        ...,
        "--code-repository",
        help="Adapter source code repository URL.",
    ),
    dataset_paths: list[str] = typer.Option(
        [],
        "--dataset-path",
        help="Path to an existing dataset Croissant JSON-LD file. Repeat for multiple datasets.",
    ),
    dataset_configs: list[str] = typer.Option(
        [],
        "--dataset-config",
        help=(
            "YAML config for a generated dataset. Repeat for multiple datasets. "
            "All generated datasets use the same --dataset-generator."
        ),
    ),
    creator: Optional[list[str]] = typer.Option(
        None,
        "--creator",
        help=(
            "Adapter creator. Accepts 'Name, Affiliation, Identifier' for "
            "croissant-baker compatibility, or 'Name|Affiliation|Identifier'. "
            "Repeat for multiple creators."
        ),
    ),
    keywords: str = typer.Option(
        ...,
        "--keywords",
        help="Comma-separated adapter keywords.",
    ),
    adapter_id: Optional[str] = typer.Option(
        None,
        "--adapter-id",
        help="Optional explicit adapter @id.",
    ),
) -> None:
    """Generate adapter metadata directly from CLI flags and dataset inputs."""
    if not creator:
        raise typer.BadParameter(
            "At least one --creator is required for adapter generation."
        )
    generated_from_blocks = _parse_dataset_blocks(ctx.args)
    generated_from_configs = [
        _dataset_request_from_config_path(config_path)
        for config_path in dataset_configs
    ]
    generated_datasets = generated_from_configs + generated_from_blocks
    if not dataset_paths and not generated_datasets:
        raise typer.BadParameter(
            "Provide at least one --dataset-path, --dataset-config, or --dataset block."
        )

    request = AdapterGenerationRequest(
        output_path=output,
        name=name,
        description=description,
        version=version,
        license_value=license_value,
        code_repository=code_repository,
        dataset_paths=dataset_paths,
        validate=validate,
        creators=creator or [],
        keywords=[item.strip() for item in keywords.split(",") if item.strip()],
        adapter_id=adapter_id,
        dataset_generator=dataset_generator,
        generated_datasets=generated_datasets,
    )
    _run_request(request=request, generator=_ADAPTER_GENERATOR)


@app.command(
    "guided",
    help=(
        "Guided mode: collect adapter metadata interactively and embed one or more "
        "existing dataset Croissant files."
    ),
)
def guided_cmd(
    dataset_generator: str = typer.Option(
        "croissant-baker",
        "--dataset-generator",
        help="Dataset generator backend used for all generated datasets in this adapter.",
    ),
    output: str = typer.Option(
        "croissant_adapter.jsonld",
        "--output",
        "-o",
        help="Destination JSON-LD file.",
    ),
) -> None:
    """Collect adapter inputs interactively and generate metadata."""
    request = prompt_for_adapter_request(
        output_path=output,
        dataset_generator=dataset_generator,
    )
    _run_request_with_recovery(request=request, generator=_ADAPTER_GENERATOR)


@app.command(
    "config",
    help=(
        "Config mode: read adapter-generation settings from YAML. Datasets can be "
        "existing Croissant files, generated through the shared dataset backend, or inline."
    ),
)
def config_cmd(
    config_path: str = typer.Option(
        ...,
        "--config",
        "-c",
        help="YAML configuration file for adapter generation.",
    ),
    dataset_generator: str = typer.Option(
        "croissant-baker",
        "--dataset-generator",
        help="Dataset generator backend used for all generated datasets in this adapter.",
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Override the output path defined in config.",
    ),
) -> None:
    """Load adapter generation input from YAML configuration and execute it."""
    try:
        request = adapter_request_from_config(
            config_path=config_path,
            output_override=output,
            dataset_generator_override=dataset_generator,
        )
    except (ValueError, typer.BadParameter) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    _run_request(request=request, generator=_ADAPTER_GENERATOR)


def _dataset_request_from_config_path(config_path: str) -> GenerationRequest:
    """Load one nested dataset request from a config file path."""
    return dataset_request_from_config(config_path=config_path)


dataset_request_from_config = _dataset_request_from_config_path


def _parse_dataset_blocks(tokens: list[str]) -> list[GenerationRequest]:
    """Parse repeated ``--dataset`` blocks into dataset generation requests."""
    if not tokens:
        return []

    datasets: list[GenerationRequest] = []
    current: dict[str, object] | None = None
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "--dataset":
            if current is not None:
                datasets.append(_build_dataset_request_from_block(current))
            current = {"creators": []}
            index += 1
            continue

        if current is None:
            raise typer.BadParameter(
                f"Unexpected argument '{token}'. Dataset block arguments must follow '--dataset'."
            )

        if token not in _DATASET_FLAG_MAP:
            raise typer.BadParameter(
                f"Unsupported dataset block option '{token}'."
            )

        if index + 1 >= len(tokens):
            raise typer.BadParameter(f"Missing value for dataset block option '{token}'.")

        value = tokens[index + 1]
        field_name = _DATASET_FLAG_MAP[token]
        if field_name == "creators":
            creators = current.setdefault("creators", [])
            assert isinstance(creators, list)
            creators.append(value)
        else:
            current[field_name] = value
        index += 2

    if current is not None:
        datasets.append(_build_dataset_request_from_block(current))

    return datasets


def _build_dataset_request_from_block(payload: dict[str, object]) -> GenerationRequest:
    """Build one nested dataset request from a parsed CLI block."""
    input_path = str(payload.get("input_path", "")).strip()
    if not input_path:
        raise typer.BadParameter("Each --dataset block must define --input or --dataset-input.")

    creators = payload.get("creators", [])
    if not isinstance(creators, list):
        creators = []

    return GenerationRequest(
        input_path=input_path,
        output_path="",
        validate=True,
        name=_optional_block_string(payload, "name"),
        description=_optional_block_string(payload, "description"),
        url=_optional_block_string(payload, "url"),
        license_value=_optional_block_string(payload, "license_value"),
        citation=_optional_block_string(payload, "citation"),
        dataset_version=_optional_block_string(payload, "dataset_version"),
        date_published=_optional_block_string(payload, "date_published"),
        creators=[str(item) for item in creators if str(item).strip()],
    )


def _optional_block_string(payload: dict[str, object], key: str) -> str | None:
    """Read an optional non-empty string from a parsed CLI payload."""
    value = payload.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def prompt_for_adapter_request(
    output_path: str,
    dataset_generator: str = "croissant-baker",
) -> AdapterGenerationRequest:
    """Interactively collect adapter metadata and nested dataset inputs."""
    console.print("\n[bold cyan]Adapter Metadata[/bold cyan]")
    console.print(
        "This guided mode collects adapter metadata and lets you embed datasets from "
        "existing Croissant files or the shared dataset generators.\n"
    )

    validate = typer.confirm("Validate generated metadata?", default=True)
    console.print(Panel.fit("[bold]Adapter Metadata[/bold]", border_style="cyan"))
    name = typer.prompt("Adapter name [required]")
    description = typer.prompt("Description [required]")
    version = _prompt_semver("Version [required]", default="0.1.0")
    license_value = typer.prompt(
        "License (URL or SPDX identifier) [required]",
        default="MIT",
    )
    code_repository = typer.prompt("Code repository URL [required]")
    selected_output = typer.prompt("Output JSON-LD file", default=output_path)
    selected_dataset_generator = typer.prompt(
        "Dataset generator backend",
        default=dataset_generator,
    )
    ensure_supported_dataset_backend(selected_dataset_generator)
    adapter_id = _prompt_optional("Adapter @id", default=slugify_identifier(name))
    keywords = _prompt_required_keywords(
        "Keywords (comma-separated, e.g. adapter,biocypher) [required]"
    )
    creators = _prompt_creators()
    dataset_paths, generated_datasets = _prompt_dataset_inputs()

    request = AdapterGenerationRequest(
        output_path=selected_output,
        name=name,
        description=description,
        version=version,
        license_value=license_value,
        code_repository=code_repository,
        dataset_paths=dataset_paths,
        validate=validate,
        creators=creators,
        keywords=keywords,
        adapter_id=adapter_id,
        dataset_generator=selected_dataset_generator,
        generated_datasets=generated_datasets,
    )

    review_adapter_request(request)
    return request


def review_adapter_request(request: AdapterGenerationRequest) -> None:
    """Show the current adapter request and let the user edit fields."""
    edit_choices = {
        "name",
        "description",
        "version",
        "license",
        "code-repository",
        "output",
        "validate",
        "dataset-generator",
        "keywords",
        "creators",
        "datasets",
        "adapter-id",
    }
    while True:
        _print_request_summary(request)
        if typer.confirm("Proceed with these values?", default=True):
            return

        choice = _prompt_choice("What do you want to edit?", edit_choices)
        if choice == "name":
            request.name = typer.prompt("Adapter name [required]", default=request.name)
        elif choice == "description":
            request.description = typer.prompt("Description [required]", default=request.description)
        elif choice == "version":
            request.version = _prompt_semver("Version [required]", default=request.version)
        elif choice == "license":
            request.license_value = typer.prompt(
                "License (URL or SPDX identifier) [required]",
                default=request.license_value,
            )
        elif choice == "code-repository":
            request.code_repository = typer.prompt(
                "Code repository URL [required]",
                default=request.code_repository,
            )
        elif choice == "output":
            request.output_path = typer.prompt("Output JSON-LD file", default=request.output_path)
        elif choice == "validate":
            request.validate = typer.confirm(
                "Validate generated metadata?",
                default=request.validate,
            )
        elif choice == "dataset-generator":
            request.dataset_generator = typer.prompt(
                "Dataset generator backend",
                default=request.dataset_generator,
            )
            ensure_supported_dataset_backend(request.dataset_generator)
        elif choice == "keywords":
            request.keywords = _prompt_required_keywords("Keywords (comma-separated) [required]")
        elif choice == "creators":
            request.creators = _prompt_creators()
        elif choice == "datasets":
            request.dataset_paths, request.generated_datasets = _prompt_dataset_inputs()
        elif choice == "adapter-id":
            request.adapter_id = _prompt_optional("Adapter @id", default=request.adapter_id or "")


def _print_request_summary(request: AdapterGenerationRequest) -> None:
    """Print a concise summary of the current adapter request."""
    console.print("\n[bold]Review adapter metadata[/bold]")
    console.print(f"  name: {request.name}")
    console.print(f"  description: {request.description}")
    console.print(f"  version: {request.version}")
    console.print(f"  license: {request.license_value}")
    console.print(f"  code-repository: {request.code_repository}")
    console.print(f"  output: {request.output_path}")
    console.print(f"  validate: {request.validate}")
    console.print(f"  dataset-generator: {request.dataset_generator}")
    console.print(f"  keywords: {', '.join(request.keywords) if request.keywords else '-'}")
    console.print(f"  adapter-id: {request.adapter_id or '-'}")
    for index, creator in enumerate(request.creators, start=1):
        console.print(f"  creator[{index}]: {creator}")
    for index, dataset_path in enumerate(request.dataset_paths, start=1):
        console.print(f"  dataset-path[{index}]: {dataset_path}")
    for index, dataset in enumerate(request.generated_datasets, start=1):
        console.print(
            f"  generated-dataset[{index}]: input={dataset.input_path}, "
            f"name={dataset.name or '-'}"
        )


def _prompt_semver(message: str, default: str = "") -> str:
    """Prompt for a version string and warn on non-semver input."""
    while True:
        value = typer.prompt(message, default=default)
        if not value:
            console.print(
                "[yellow]Version cannot be empty. Please enter a version string.[/yellow]"
            )
            continue
        if not _SEMVER_RE.match(value):
            console.print(
                f"[yellow]Note: '{value}' does not follow MAJOR.MINOR.PATCH.[/yellow]"
            )
        return value


def _prompt_optional(label: str, default: str = "") -> str | None:
    """Prompt for an optional string value."""
    value = typer.prompt(label, default=default)
    return value or None


def _prompt_required_keywords(label: str) -> list[str]:
    """Prompt until at least one keyword is provided."""
    while True:
        raw = typer.prompt(label)
        keywords = [k.strip() for k in raw.split(",") if k.strip()]
        if keywords:
            return keywords
        console.print("[red]At least one keyword is required.[/red]")


def _prompt_creators() -> list[str]:
    """Collect one or more adapter creators interactively."""
    console.print("\n[bold]Creators / developers[/bold]")
    console.print("At least one creator is required.\n")
    creators: list[str] = []
    while True:
        name = typer.prompt("  Full name [required]")
        affiliation = typer.prompt("  Affiliation [optional]", default="")
        identifier = typer.prompt("  ORCID or identifier [optional]", default="")
        creators.append(", ".join(part for part in [name, affiliation, identifier] if part))
        if not typer.confirm("Add another creator?", default=False):
            break
    return creators


def _prompt_dataset_inputs() -> tuple[list[str], list[GenerationRequest]]:
    """Collect embedded dataset inputs for the adapter request."""
    console.print(Panel.fit("[bold]Embedded Dataset Metadata[/bold]", border_style="magenta"))
    console.print(
        "Each embedded dataset can come from an existing Croissant file, a shared dataset "
        "generator run.\n"
    )
    dataset_paths: list[str] = []
    generated_datasets: list[GenerationRequest] = []
    while True:
        dataset_mode = _prompt_choice(
            "How do you want to add this dataset?",
            {"existing", "generate"},
            default="existing",
        )
        if dataset_mode == "existing":
            dataset_paths.append(typer.prompt("  Dataset metadata path [required]"))
        else:
            generated_datasets.append(_prompt_generated_dataset())
        if not typer.confirm("Add another dataset?", default=False):
            break
    return dataset_paths, generated_datasets


def _prompt_generated_dataset() -> GenerationRequest:
    """Collect one generated dataset request interactively."""
    console.print("\n[cyan]Generated dataset[/cyan]")
    input_path = typer.prompt("  Input path [required]")
    name = _prompt_optional("  Dataset name")
    description = _prompt_optional("  Description")
    url = _prompt_optional("  Dataset URL")
    license_value = _prompt_optional("  License")
    citation = _prompt_optional("  Citation")
    dataset_version = _prompt_optional("  Dataset version", default="0.1.0")
    date_published = _prompt_optional("  Date published (YYYY-MM-DD)")
    creators: list[str] = []
    while typer.confirm("  Add a dataset creator?", default=not creators):
        creators.append(_prompt_dataset_creator())
    return GenerationRequest(
        input_path=input_path,
        output_path="",
        validate=True,
        name=name,
        description=description,
        url=url,
        license_value=license_value,
        citation=citation,
        dataset_version=dataset_version,
        date_published=date_published,
        creators=creators,
    )


def _prompt_dataset_creator() -> str:
    """Collect one dataset creator in compact serialized form."""
    name = typer.prompt("    Creator name [required]")
    email = typer.prompt("    Creator email [optional]", default="")
    url = typer.prompt("    Creator URL [optional]", default="")
    return ", ".join(part for part in [name, email, url] if part)


def _prompt_choice(
    label: str,
    choices: set[str],
    default: str | None = None,
) -> str:
    """Prompt until one of the allowed lowercased choices is selected."""
    ordered = sorted(choices)
    prompt = f"{label} ({', '.join(ordered)})"
    while True:
        value = typer.prompt(prompt, default=default or ordered[0]).strip().lower()
        if value in choices:
            return value
        console.print(f"[yellow]Choose one of: {', '.join(ordered)}[/yellow]")
