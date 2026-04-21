"""Interactive and scripted CLI commands for dataset metadata generation."""

from __future__ import annotations

import shlex
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from src.core.dataset.config import request_from_config
from src.core.dataset.request import (
    GenerationRequest as DatasetGenerationRequest,
    GenerationResult,
)
from src.core.dataset.service import (
    build_croissant_baker_command,
    ensure_supported_generator,
    execute_request,
)


console = Console()
app = typer.Typer(
    help="Generate dataset Croissant metadata using pluggable generators.",
    no_args_is_help=True,
)


def _run_request(
    request: DatasetGenerationRequest,
    generator: str,
    mode: str,
) -> None:
    """Execute one dataset request and render the completion banner."""
    try:
        result = _execute_with_status(
            request=request,
            generator=generator,
            mode=mode,
        )
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    _print_completion_banner(
        request=request,
        generator=generator,
        mode=mode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def _run_request_with_recovery(request: DatasetGenerationRequest, generator: str) -> None:
    """Execute a guided dataset request and allow edits after failures."""
    mode = "guided"
    while True:
        try:
            result = _execute_with_status(
                request=request,
                generator=generator,
                mode=mode,
            )
        except RuntimeError as exc:
            console.print(f"[red]{exc}[/red]")
            if not typer.confirm(
                "Edit the guided input data and retry?",
                default=True,
            ):
                raise typer.Exit(code=1) from exc
            review_request(request)
            continue

        _print_completion_banner(
            request=request,
            generator=generator,
            mode=mode,
            stdout=result.stdout,
            stderr=result.stderr,
        )
        return


def _announce_generator_run(
    request: DatasetGenerationRequest,
    generator: str,
    mode: str,
) -> Panel:
    """Build the status panel shown while a dataset request is running."""
    body = Text()
    body.append("Mode\n", style="bold magenta")
    body.append(f"{mode}\n\n", style="white")
    body.append("Generator\n", style="bold cyan")
    body.append(f"{generator}\n\n", style="white")
    body.append("Input\n", style="bold")
    body.append(f"{request.input_path}\n\n", style="white")
    body.append("Output\n", style="bold")
    body.append(f"{request.output_path}", style="white")

    return Panel(
        body,
        title="Dataset Generation",
        border_style="cyan",
        expand=False,
    )


def _execute_with_status(
    request: DatasetGenerationRequest,
    generator: str,
    mode: str,
) -> GenerationResult:
    """Run a dataset request while showing a live status spinner."""
    panel = _announce_generator_run(
        request=request,
        generator=generator,
        mode=mode,
    )
    with console.status(panel, spinner="dots"):
        return execute_request(request=request, generator=generator)


def _print_completion_banner(
    request: DatasetGenerationRequest,
    generator: str,
    mode: str,
    stdout: str,
    stderr: str,
) -> None:
    """Render the final success banner and backend report."""
    body = Text()
    body.append("Status\n", style="bold green")
    body.append("Generation completed successfully\n\n", style="white")
    body.append("Mode\n", style="bold magenta")
    body.append(f"{mode}\n\n", style="white")
    body.append("Generator\n", style="bold cyan")
    body.append(f"{generator}\n\n", style="white")
    body.append("Output\n", style="bold")
    body.append(f"{request.output_path}", style="white")

    console.print(
        Panel(
            body,
            title="Dataset Ready",
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
        stdout_body = Text("\n\n".join(report_parts), style="white")
        console.print(
            Panel(
                stdout_body,
                title=f"{generator} Report",
                border_style="cyan",
                expand=False,
            )
        )


@app.command(
    "guided",
    help="Guided mode: collect dataset metadata interactively, preview the backend command, and run the selected generator.",
)
def guided_cmd(
    generator: str = typer.Option(
        "croissant-baker",
        "--generator",
        help="Dataset generator implementation.",
    ),
    input_path: Optional[str] = typer.Option(
        None,
        "--input",
        help="Dataset directory passed to the selected generator.",
    ),
    output: str = typer.Option(
        "croissant.jsonld",
        "--output",
        "-o",
        help="Destination JSON-LD file.",
    ),
) -> None:
    """Collect dataset metadata interactively and generate a document."""
    ensure_supported_generator(generator)
    request = prompt_for_request(
        input_path=input_path,
        output_path=output,
        generator=generator,
    )
    _run_request_with_recovery(request=request, generator=generator)


@app.command(
    "config",
    help="Config mode: read dataset-generation settings from YAML, map them to generator arguments, and run the selected generator.",
)
def config_cmd(
    config_path: str = typer.Option(
        ...,
        "--config",
        "-c",
        help="YAML configuration file for dataset generation.",
    ),
    generator: str = typer.Option(
        "croissant-baker",
        "--generator",
        help="Dataset generator implementation.",
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Override the output path defined in config.",
    ),
) -> None:
    """Load dataset generation input from YAML configuration and execute it."""
    ensure_supported_generator(generator)
    request = request_from_config(config_path=config_path, output_override=output)
    _run_request(request=request, generator=generator, mode="config")


@app.command(
    "direct",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    help="Direct mode: act as a thin wrapper around the selected generator while still supporting common dataset flags.",
)
def direct_cmd(
    ctx: typer.Context,
    generator: str = typer.Option(
        "croissant-baker",
        "--generator",
        help="Dataset generator implementation.",
    ),
    input_path: str = typer.Option(
        ...,
        "--input",
        help="Dataset directory passed to the selected generator.",
    ),
    output: str = typer.Option(
        "croissant.jsonld",
        "--output",
        "-o",
        help="Destination JSON-LD file.",
    ),
    validate: bool = typer.Option(
        True,
        "--validate/--no-validate",
        help="Run generator validation when supported.",
    ),
    name: Optional[str] = typer.Option(None, "--name", help="Dataset name."),
    description: Optional[str] = typer.Option(
        None, "--description", help="Dataset description."
    ),
    url: Optional[str] = typer.Option(None, "--url", help="Dataset URL."),
    license_value: Optional[str] = typer.Option(
        None, "--license", help="Dataset license."
    ),
    citation: Optional[str] = typer.Option(
        None, "--citation", help="Dataset citation."
    ),
    dataset_version: Optional[str] = typer.Option(
        None, "--dataset-version", help="Dataset version."
    ),
    date_published: Optional[str] = typer.Option(
        None, "--date-published", help="Dataset publication date."
    ),
    creators: list[str] = typer.Option(
        None,
        "--creator",
        help="Creator as 'name[,email[,url]]'. Repeat to add more.",
    ),
) -> None:
    """Pass explicit dataset flags directly to the selected backend."""
    ensure_supported_generator(generator)
    request = DatasetGenerationRequest(
        input_path=input_path,
        output_path=output,
        validate=validate,
        name=name,
        description=description,
        url=url,
        license_value=license_value,
        citation=citation,
        dataset_version=dataset_version,
        date_published=date_published,
        creators=creators or [],
        extra_args=list(ctx.args),
    )
    _run_request(request=request, generator=generator, mode="direct")


def prompt_for_request(
    input_path: str | None,
    output_path: str,
    generator: str = "croissant-baker",
) -> DatasetGenerationRequest:
    """Interactively collect dataset metadata for one generation run."""
    console.print("\n[bold cyan]Dataset Generator[/bold cyan]")
    console.print("This guided mode collects metadata and then runs the selected generator.\n")

    selected_input = input_path or typer.prompt("Dataset input directory [required]")
    selected_output = typer.prompt("Output JSON-LD file", default=output_path)
    validate = typer.confirm("Validate generated metadata?", default=True)

    name = _prompt_optional("Dataset name")
    description = _prompt_optional("Description")
    url = _prompt_optional("Dataset URL")
    license_value = _prompt_optional("License")
    citation = _prompt_optional("Citation")
    dataset_version = _prompt_optional("Dataset version", default="0.1.0")
    date_published = _prompt_optional("Date published (YYYY-MM-DD)")

    creators: list[str] = []
    while typer.confirm("Add a creator?", default=not creators):
        creator_name = typer.prompt("  Creator name [required]")
        creator_email = typer.prompt("  Creator email [optional]", default="")
        creator_url = typer.prompt("  Creator URL [optional]", default="")
        creators.append(_format_creator(creator_name, creator_email, creator_url))

    request = DatasetGenerationRequest(
        input_path=selected_input,
        output_path=selected_output,
        validate=validate,
        name=name,
        description=description,
        url=url,
        license_value=license_value,
        citation=citation,
        dataset_version=dataset_version,
        date_published=date_published,
        creators=creators,
    )

    review_request(request)

    console.print("\n[bold]Command preview[/bold]")
    console.print(_format_request_preview(request=request, generator=generator))
    if not typer.confirm("Run this command?", default=True):
        raise typer.Abort()

    return request


def _prompt_optional(label: str, default: str = "") -> str | None:
    """Prompt for an optional string value."""
    value = typer.prompt(label, default=default)
    return value or None


def review_request(request: DatasetGenerationRequest) -> None:
    """Show the current dataset request and let the user edit fields."""
    edit_choices = {
        "input",
        "output",
        "validate",
        "name",
        "description",
        "url",
        "license",
        "citation",
        "dataset-version",
        "date-published",
        "creators",
    }
    while True:
        _print_request_summary(request)
        if typer.confirm("Proceed with these values?", default=True):
            return

        choice = _prompt_choice(
            "What do you want to edit?",
            edit_choices,
        )

        if choice == "input":
            request.input_path = typer.prompt(
                "Dataset input directory [required]",
                default=request.input_path,
            )
        elif choice == "output":
            request.output_path = typer.prompt(
                "Output JSON-LD file",
                default=request.output_path,
            )
        elif choice == "validate":
            request.validate = typer.confirm(
                "Validate generated metadata?",
                default=request.validate,
            )
        elif choice == "name":
            request.name = _prompt_optional("Dataset name", default=request.name or "")
        elif choice == "description":
            request.description = _prompt_optional(
                "Description", default=request.description or ""
            )
        elif choice == "url":
            request.url = _prompt_optional("Dataset URL", default=request.url or "")
        elif choice == "license":
            request.license_value = _prompt_optional(
                "License", default=request.license_value or ""
            )
        elif choice == "citation":
            request.citation = _prompt_optional(
                "Citation", default=request.citation or ""
            )
        elif choice == "dataset-version":
            request.dataset_version = _prompt_optional(
                "Dataset version", default=request.dataset_version or ""
            )
        elif choice == "date-published":
            request.date_published = _prompt_optional(
                "Date published (YYYY-MM-DD)",
                default=request.date_published or "",
            )
        elif choice == "creators":
            request.creators = _edit_creators(request.creators)


def _print_request_summary(request: DatasetGenerationRequest) -> None:
    """Print a concise summary of the current dataset request."""
    console.print("\n[bold]Review dataset metadata[/bold]")
    console.print(f"  input: {request.input_path}")
    console.print(f"  output: {request.output_path}")
    console.print(f"  validate: {request.validate}")
    console.print(f"  name: {request.name or '-'}")
    console.print(f"  description: {request.description or '-'}")
    console.print(f"  url: {request.url or '-'}")
    console.print(f"  license: {request.license_value or '-'}")
    console.print(f"  citation: {request.citation or '-'}")
    console.print(f"  dataset-version: {request.dataset_version or '-'}")
    console.print(f"  date-published: {request.date_published or '-'}")
    if request.creators:
        for index, creator in enumerate(request.creators, start=1):
            console.print(f"  creator[{index}]: {creator}")
    else:
        console.print("  creators: -")


def _edit_creators(creators: list[str]) -> list[str]:
    """Edit the list of serialized dataset creators interactively."""
    creator_actions = {"add", "replace", "remove", "done"}
    while True:
        console.print("\n[bold]Creators[/bold]")
        if creators:
            for index, creator in enumerate(creators, start=1):
                console.print(f"  {index}. {creator}")
        else:
            console.print("  No creators defined.")

        action = _prompt_choice(
            "Choose creator action",
            creator_actions,
            default="done",
        )

        if action == "done":
            return creators
        if action == "add":
            creators.append(_prompt_creator())
            continue
        if action == "replace":
            if not creators:
                console.print("[yellow]There are no creators to replace.[/yellow]")
                continue
            index = typer.prompt("Creator number to replace", type=int)
            if 1 <= index <= len(creators):
                creators[index - 1] = _prompt_creator(existing=creators[index - 1])
            else:
                console.print("[yellow]Invalid creator number.[/yellow]")
            continue
        if action == "remove":
            if not creators:
                console.print("[yellow]There are no creators to remove.[/yellow]")
                continue
            index = typer.prompt("Creator number to remove", type=int)
            if 1 <= index <= len(creators):
                creators.pop(index - 1)
            else:
                console.print("[yellow]Invalid creator number.[/yellow]")


def _prompt_creator(existing: str = "") -> str:
    """Collect one dataset creator, optionally seeded from an existing value."""
    default_name = ""
    default_email = ""
    default_url = ""
    if existing:
        parts = existing.split(",")
        default_name = parts[0] if len(parts) > 0 else ""
        default_email = parts[1] if len(parts) > 1 else ""
        default_url = parts[2] if len(parts) > 2 else ""

    creator_name = typer.prompt("  Creator name [required]", default=default_name)
    creator_email = typer.prompt("  Creator email [optional]", default=default_email)
    creator_url = typer.prompt("  Creator URL [optional]", default=default_url)
    return _format_creator(creator_name, creator_email, creator_url)


def _prompt_choice(label: str, options: set[str], default: str | None = None) -> str:
    """Prompt until one of the allowed lowercased options is selected."""
    sorted_options = sorted(options)
    hint = "/".join(sorted_options)
    while True:
        prompt_label = f"{label} [{hint}]"
        value = typer.prompt(prompt_label, default=default or "").strip().lower()
        if value in options:
            return value
        console.print(
            f"[yellow]Invalid choice '{value}'. Choose one of: {', '.join(sorted_options)}.[/yellow]"
        )


def _format_command_preview(command: list[str]) -> str:
    """Format a shell command as a multi-line fenced code block."""
    if not command:
        return ""

    lines = [shlex.quote(command[0]) + " \\"]
    index = 1
    while index < len(command):
        current = shlex.quote(command[index])
        next_token_is_value = (
            index + 1 < len(command) and not command[index + 1].startswith("--")
        )
        if next_token_is_value:
            current = f"{current} {shlex.quote(command[index + 1])}"
            index += 1
        suffix = " \\" if index < len(command) - 1 else ""
        lines.append(f"{current}{suffix}")
        index += 1

    return "```bash\n" + "\n".join(lines) + "\n```"


def _format_request_preview(
    request: DatasetGenerationRequest,
    generator: str,
) -> str:
    """Render a preview of the backend invocation for the current request."""
    if generator == "croissant-baker":
        return _format_command_preview(build_croissant_baker_command(request))

    lines = [
        f"generator: {generator}",
        f"input: {request.input_path}",
        f"output: {request.output_path}",
        f"validate: {request.validate}",
    ]
    if request.name:
        lines.append(f"name: {request.name}")
    if request.description:
        lines.append(f"description: {request.description}")
    if request.url:
        lines.append(f"url: {request.url}")
    if request.license_value:
        lines.append(f"license: {request.license_value}")
    if request.citation:
        lines.append(f"citation: {request.citation}")
    if request.dataset_version:
        lines.append(f"dataset-version: {request.dataset_version}")
    if request.date_published:
        lines.append(f"date-published: {request.date_published}")
    if request.creators:
        lines.extend(f"creator: {creator}" for creator in request.creators)
    return "```text\n" + "\n".join(lines) + "\n```"


def _format_creator(name: str, email: str, url: str) -> str:
    """Serialize dataset creator fields into the compact CLI format."""
    parts = [name]
    if email or url:
        parts.append(email)
    if url:
        if not email:
            parts.append("")
        parts.append(url)
    return ",".join(parts)
