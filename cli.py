from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.core.adapter.discovery import (
    discover_local_adapter,
    discover_remote_adapter,
    validate_discovered_adapter,
)
from src.core.adapter.cli import app as adapter_app
from src.core.adapter.service import create_registration_request
from src.core.dataset.cli import app as dataset_app
from src.core.registration.service import (
    finish_registration as finish_registration_record,
)
from src.core.registration.service import (
    refresh_active_registrations as refresh_active_registrations_record,
)
from src.core.registration.service import (
    revalidate_registration as revalidate_registration_record,
)
from src.core.registration.service import (
    submit_registration as submit_registration_record,
)
from src.core.registration.models import (
    BatchRefreshRecord,
    RegistrationEvent,
    RegistryEntry,
    StoredRegistration,
)
from src.core.shared.constants import METADATA_FILENAME
from src.core.shared.files import fetch_local_metadata, parse_json_metadata
from src.core.settings import settings as core_settings
from src.core.validation import (
    validate_adapter_with_embedded_datasets,
    validate_dataset,
)
from src.core.validation.results import ValidationResult
from src.persistence.factory import build_registration_store

_DEFAULT_GITHUB_LOGIN = "sampleGithubLogin"
_DEMO_GITHUB_LOGIN = "jmsssc"
STYLE_SECTION_HEADING = "bold cyan"
REGISTRATION_ID_HELP = "Stored registration identifier."
HTTPS_SCHEME = "https"
HTTP_SCHEME = "http"
JSONLD_TYPE = "@type"

_DB_PATH_HELP = (
    "SQLite database path for stored registrations. Defaults to "
    f"{core_settings.registry_db_path_env} or "
    f"{core_settings.default_registry_db_path}."
)

_DEMO_ADAPTERS: list[dict[str, Any]] = [
    {
        "adapter_name": "Pathway Signals Adapter",
        "adapter_id": "pathway-signals-adapter",
        "version": "0.1.0",
        "repository_location": "https://github.com/biocypher/pathway-signals-adapter",
        "description": "Generic pathway and interaction data adapter for registry demos.",
        "keywords": ["pathways", "interactions", "demo"],
        "data_source": "Pathway Signals",
    },
    {
        "adapter_name": "Sample Omics Adapter",
        "adapter_id": "sample-omics-adapter",
        "version": "0.1.0",
        "repository_location": "https://github.com/biocypher/sample-omics-adapter",
        "doi": "10.5555/12345678",
        "description": "Example adapter describing lightweight multi-omics sample annotations.",
        "keywords": ["omics", "samples", "demo"],
        "data_source": "Sample Omics",
    },
    {
        "adapter_name": "Reference Nodes Adapter",
        "adapter_id": "reference-nodes-adapter",
        "version": "0.1.0",
        "repository_location": "https://github.com/biocypher/reference-nodes-adapter",
        "description": "Small demo adapter for reference node and edge metadata examples.",
        "keywords": ["reference", "graph", "demo"],
        "data_source": "Reference Nodes",
    },
]

app = typer.Typer(
    name="biocypher-registry",
    help="Manage BioCypher adapter and dataset metadata.",
    no_args_is_help=True,
)
console = Console()
app.add_typer(dataset_app, name="dataset")
app.add_typer(adapter_app, name="adapter")


def _demo_adapter_metadata(spec: dict[str, Any]) -> dict[str, Any]:
    adapter_id = str(spec["adapter_id"])
    data_source = str(spec["data_source"])
    return {
        JSONLD_TYPE: "SoftwareSourceCode",
        "@id": adapter_id,
        "name": spec["adapter_name"],
        "description": spec["description"],
        "version": spec["version"],
        "license": "MIT",
        "codeRepository": spec["repository_location"],
        "programmingLanguage": "Python",
        "targetProduct": "BioCypher",
        "creator": [{JSONLD_TYPE: "Person", "name": _DEMO_GITHUB_LOGIN}],
        "keywords": spec["keywords"],
        "hasPart": [
            {
                JSONLD_TYPE: "sc:Dataset",
                "name": data_source,
                "description": f"Vague demo dataset backing the {spec['adapter_name']}.",
                "version": "2026.1",
                "license": "MIT",
                "url": f"https://example.org/{adapter_id}",
                "recordSet": [
                    {
                        "name": f"{adapter_id}-records",
                        "field": [
                            {"name": "source", "description": "Source identifier"},
                            {"name": "target", "description": "Target identifier"},
                            {"name": "score", "description": "Demo confidence score"},
                        ],
                    }
                ],
            }
        ],
    }


def _load_metadata(path: Path) -> dict[str, Any]:
    if path.is_dir():
        _, metadata = fetch_local_metadata(path)
        return metadata

    if path.is_file():
        content = path.read_text(encoding="utf-8")
        return parse_json_metadata(content, str(path))

    raise FileNotFoundError(f"Path not found: {path}")


def _detect_metadata_kind(metadata: dict[str, Any]) -> str:
    root_type = metadata.get(JSONLD_TYPE)
    if root_type in {"Dataset", "sc:Dataset"}:
        return "dataset"
    if root_type in {"SoftwareSourceCode", "sc:SoftwareSourceCode"}:
        return "adapter"
    raise typer.BadParameter(
        "Could not detect metadata type automatically. "
        "Expected root '@type' to be 'Dataset', 'sc:Dataset', "
        "'SoftwareSourceCode', or 'sc:SoftwareSourceCode'."
    )


def _run_validation(metadata: dict[str, Any], kind: str) -> ValidationResult:
    if kind == "dataset":
        return validate_dataset(metadata)
    return validate_adapter_with_embedded_datasets(metadata)


def _validate_path(path: str, kind: str | None = None) -> None:
    try:
        metadata = _load_metadata(Path(path))
    except (ValueError, OSError, typer.BadParameter) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    resolved_kind = kind or _detect_metadata_kind(metadata)
    _print_validation_target(path, resolved_kind)
    result = _run_validation(metadata, resolved_kind)
    _print_validation_result(result, resolved_kind)


# ============================================================================
# Console rendering helpers
# ============================================================================


def _print_validation_result(
    result: ValidationResult,
    kind: str,
) -> None:
    _print_validation_checks(result)

    if result.is_valid:
        console.print(
            f"[green]VALID[/green] {kind} metadata (profile: {result.profile_version})"
        )
        return

    console.print(
        f"[red]INVALID[/red] {kind} metadata (profile: {result.profile_version})"
    )
    for err in result.errors:
        console.print(f"  • {err}")
    raise typer.Exit(code=1)


def _print_validation_checks(result: ValidationResult) -> None:
    if not result.checks:
        return

    table = Table(title="Validation Checks")
    table.add_column("Check", style="cyan")
    table.add_column("Status")
    for check in result.checks:
        status = "[green]PASS[/green]" if check.is_valid else "[red]FAIL[/red]"
        table.add_row(check.name, status)
    console.print(table)


def _print_validation_target(path: str, kind: str) -> None:
    body = Text()
    body.append("Detected Type\n", style=STYLE_SECTION_HEADING)
    body.append(f"{kind}\n\n", style="white")
    body.append("Input\n", style="bold")
    body.append(path, style="white")
    console.print(
        Panel(
            body,
            title="Validation Target",
            border_style="cyan",
            expand=False,
        )
    )


def _print_discovery_target(
    source: str,
    metadata_path: str | None,
    location_kind: str,
) -> None:
    body = Text()
    body.append("Source\n", style=STYLE_SECTION_HEADING)
    body.append(f"{source}\n\n", style="white")
    body.append("Location\n", style="bold")
    body.append(f"{location_kind}\n\n", style="white")
    body.append("Metadata\n", style="bold")
    body.append(metadata_path or METADATA_FILENAME, style="white")
    console.print(
        Panel(
            body,
            title="Discovery Target",
            border_style="cyan",
            expand=False,
        )
    )


def _print_submission_request(
    adapter_name: str,
    adapter_id: str,
    repository_location: str,
    repository_kind: str,
    github_login: str,
) -> None:
    body = Text()
    body.append("Adapter\n", style=STYLE_SECTION_HEADING)
    body.append(f"{adapter_name}\n\n", style="white")
    body.append("Adapter ID\n", style="bold")
    body.append(f"{adapter_id}\n\n", style="white")
    body.append("Repository\n", style="bold")
    body.append(f"{repository_location}\n\n", style="white")
    body.append("Kind\n", style="bold")
    body.append(f"{repository_kind}\n\n", style="white")
    body.append("GitHub Login\n", style="bold")
    body.append(github_login, style="white")
    console.print(
        Panel(
            body,
            title="Registration Request",
            border_style="cyan",
            expand=False,
        )
    )


def _print_registration_result(
    registration_id: str,
    adapter_name: str,
    status: str,
    profile_version: str | None,
    metadata_path: str | None,
    validation_errors: list[str] | None = None,
) -> None:
    body = Text()
    body.append("Registration ID\n", style=STYLE_SECTION_HEADING)
    body.append(f"{registration_id}\n\n", style="white")
    body.append("Adapter\n", style="bold")
    body.append(f"{adapter_name}\n\n", style="white")
    body.append("Status\n", style="bold")
    body.append(f"{status}\n\n", style="white")
    body.append("Profile\n", style="bold")
    body.append(f"{profile_version or 'n/a'}\n\n", style="white")
    body.append("Metadata\n", style="bold")
    body.append(metadata_path or METADATA_FILENAME, style="white")
    if validation_errors:
        body.append("\n\nErrors\n", style="bold")
        body.append("\n".join(validation_errors), style="white")
    console.print(
        Panel(
            body,
            title="Registration Result",
            border_style="cyan",
            expand=False,
        )
    )


def _print_batch_refresh_summary(
    active_sources: int,
    processed: int,
    valid_created: int,
    unchanged: int,
    invalid: int,
    duplicate: int,
    rejected_same_version_changed: int,
    fetch_failed: int,
) -> None:
    table = Table(title="Batch Refresh Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", justify="right")
    table.add_row("Active sources", str(active_sources))
    table.add_row("Processed", str(processed))
    table.add_row("VALID_CREATED", str(valid_created))
    table.add_row("UNCHANGED", str(unchanged))
    table.add_row("INVALID", str(invalid))
    table.add_row("DUPLICATE", str(duplicate))
    table.add_row(
        "REJECTED_SAME_VERSION_CHANGED",
        str(rejected_same_version_changed),
    )
    table.add_row("FETCH_FAILED", str(fetch_failed))
    console.print(table)


def _print_latest_batch_refresh(refresh: BatchRefreshRecord) -> None:
    """Print the latest persisted batch refresh summary."""
    body = Text()
    body.append("Refresh ID\n", style=STYLE_SECTION_HEADING)
    body.append(f"{refresh.refresh_id}\n\n", style="white")
    body.append("Started At\n", style="bold")
    body.append(f"{refresh.started_at.isoformat()}\n\n", style="white")
    body.append("Finished At\n", style="bold")
    body.append(refresh.finished_at.isoformat(), style="white")
    console.print(
        Panel(
            body,
            title="Latest Batch Refresh",
            border_style="cyan",
            expand=False,
        )
    )
    _print_batch_refresh_summary(
        active_sources=refresh.active_sources,
        processed=refresh.processed,
        valid_created=refresh.valid_created,
        unchanged=refresh.unchanged,
        invalid=refresh.invalid,
        duplicate=refresh.duplicate,
        rejected_same_version_changed=refresh.rejected_same_version_changed,
        fetch_failed=refresh.fetch_failed,
    )


def _print_stored_registration(
    registration_id: str,
    adapter_name: str,
    repository_location: str,
    repository_kind: str,
    status: str,
    github_login: str,
) -> None:
    body = Text()
    body.append("Registration ID\n", style=STYLE_SECTION_HEADING)
    body.append(f"{registration_id}\n\n", style="white")
    body.append("Adapter\n", style="bold")
    body.append(f"{adapter_name}\n\n", style="white")
    body.append("Repository\n", style="bold")
    body.append(f"{repository_location}\n\n", style="white")
    body.append("Kind\n", style="bold")
    body.append(f"{repository_kind}\n\n", style="white")
    body.append("Status\n", style="bold")
    body.append(f"{status}\n\n", style="white")
    body.append("GitHub Login\n", style="bold")
    body.append(github_login, style="white")
    console.print(
        Panel(
            body,
            title="Stored Registration",
            border_style="cyan",
            expand=False,
        )
    )


def _print_registration_table(
    registrations: list[tuple[StoredRegistration, str]],
) -> None:
    """Print stored registrations in a compact table."""
    table = Table(title="Stored Registrations")
    table.add_column("Registration ID", style="cyan")
    table.add_column("Adapter")
    table.add_column("Status")
    table.add_column("Latest Event")
    table.add_column("Kind")
    table.add_column("Last Checked")
    for registration, latest_event in registrations:
        table.add_row(
            registration.registration_id,
            registration.adapter_name,
            registration.status.value,
            latest_event,
            registration.repository_kind,
            registration.last_checked_at.isoformat()
            if registration.last_checked_at is not None
            else "Not processed yet",
        )
    console.print(table)


def _print_registration_events(events: list[RegistrationEvent]) -> None:
    """Print one registration's event history."""
    table = Table(title="Registration Events")
    table.add_column("Event", style="cyan")
    table.add_column("Message")
    table.add_column("Profile")
    table.add_column("Checksum")
    table.add_column("Finished At")
    for event in events:
        table.add_row(
            event.event_type,
            event.message or "",
            event.profile_version or "n/a",
            event.observed_checksum or "n/a",
            event.finished_at.isoformat(),
        )
    console.print(table)


def _print_registry_entries(entries: list[RegistryEntry]) -> None:
    """Print active canonical registry entries."""
    table = Table(title="Registry Entries")
    table.add_column("Entry ID", style="cyan")
    table.add_column("Adapter")
    table.add_column("Version")
    table.add_column("Uniqueness Key")
    table.add_column("Profile")
    table.add_column("Updated At")
    for entry in entries:
        table.add_row(
            entry.entry_id,
            entry.adapter_name,
            entry.adapter_version or "n/a",
            entry.uniqueness_key,
            entry.profile_version or "n/a",
            entry.updated_at.isoformat(),
        )
    console.print(table)


# ============================================================================
# CLI commands
# ============================================================================


def _resolve_github_login(github_login: str | None) -> str:
    if github_login is None:
        return _DEFAULT_GITHUB_LOGIN
    normalized_login = github_login.strip()
    return normalized_login or _DEFAULT_GITHUB_LOGIN


@app.command(
    "submit",
    help=(
        "Submit an adapter name and repository location to create a registration "
        "request for the registry workflow."
    ),
)
def submit_cmd(
    adapter_name: str = typer.Option(
        ...,
        "--name",
        help="Human-readable adapter name.",
    ),
    repository_location: str = typer.Argument(
        ...,
        help="Local repository path or supported repository URL.",
    ),
    github_login: str | None = typer.Option(
        _DEFAULT_GITHUB_LOGIN,
        "--github-login",
        help="GitHub login to attach to this registration.",
    ),
) -> None:
    resolved_github_login = _resolve_github_login(github_login)
    try:
        request = create_registration_request(
            adapter_name=adapter_name,
            repository_location=repository_location,
            submitted_by_github_login=resolved_github_login,
        )
    except (ValueError, OSError, typer.BadParameter) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    _print_submission_request(
        adapter_name=request.adapter_name,
        adapter_id=request.adapter_id,
        repository_location=request.repository_location,
        repository_kind=request.repository_kind,
        github_login=request.submitted_by_github_login or _DEFAULT_GITHUB_LOGIN,
    )
    console.print("[green]Registration request created[/green]")


@app.command(
    "submit-registration",
    help=("Submit and persist an adapter registration in the configured database."),
)
def submit_registration_cmd(
    adapter_name: str = typer.Option(
        ...,
        "--name",
        help="Human-readable adapter name.",
    ),
    repository_location: str = typer.Argument(
        ...,
        help="Local repository path or supported repository URL.",
    ),
    db_path: str | None = typer.Option(
        None,
        "--db-path",
        help=_DB_PATH_HELP,
    ),
    github_login: str | None = typer.Option(
        _DEFAULT_GITHUB_LOGIN,
        "--github-login",
        help="GitHub login to attach to this registration.",
    ),
) -> None:
    resolved_github_login = _resolve_github_login(github_login)
    try:
        store = build_registration_store(db_path)
        registration = submit_registration_record(
            adapter_name=adapter_name,
            repository_location=repository_location,
            store=store,
            submitted_by_github_login=resolved_github_login,
        )
    except (ValueError, OSError, typer.BadParameter) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    _print_stored_registration(
        registration_id=registration.registration_id,
        adapter_name=registration.adapter_name,
        repository_location=registration.repository_location,
        repository_kind=registration.repository_kind,
        status=registration.status.value,
        github_login=registration.submitted_by_github_login or _DEFAULT_GITHUB_LOGIN,
    )
    console.print("[green]Registration stored[/green]")


@app.command(
    "finish-registration",
    help=(
        "Discover, validate, and persist one stored registration as VALID "
        "using the configured database."
    ),
)
def finish_registration_cmd(
    registration_id: str = typer.Argument(..., help=REGISTRATION_ID_HELP),
    db_path: str | None = typer.Option(
        None,
        "--db-path",
        help=_DB_PATH_HELP,
    ),
) -> None:
    try:
        store = build_registration_store(db_path)
        registration = finish_registration_record(
            registration_id=registration_id,
            store=store,
        )
    except (ValueError, OSError, typer.BadParameter) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    _print_registration_result(
        registration_id=registration.registration_id,
        adapter_name=registration.adapter_name,
        status=registration.status.value,
        profile_version=registration.profile_version,
        metadata_path=registration.metadata_path,
        validation_errors=registration.validation_errors,
    )
    if registration.status.value == "INVALID":
        console.print("[red]Registration finished with validation errors[/red]")
        raise typer.Exit(code=1)
    console.print("[green]Registration finished[/green]")


@app.command(
    "refresh-registry",
    help=(
        "Process all active stored registrations once and continue past per-source failures."
    ),
)
def refresh_registry_cmd(
    db_path: str | None = typer.Option(
        None,
        "--db-path",
        help=_DB_PATH_HELP,
    ),
) -> None:
    try:
        store = build_registration_store(db_path)
        summary = refresh_active_registrations_record(store=store)
    except (ValueError, OSError, typer.BadParameter) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    _print_batch_refresh_summary(
        active_sources=summary.active_sources,
        processed=summary.processed,
        valid_created=summary.valid_created,
        unchanged=summary.unchanged,
        invalid=summary.invalid,
        duplicate=summary.duplicate,
        rejected_same_version_changed=summary.rejected_same_version_changed,
        fetch_failed=summary.fetch_failed,
    )
    console.print("[green]Batch refresh finished[/green]")


@app.command(
    "revalidate-registration",
    help="Reprocess one previously invalid or fetch-failed registration immediately.",
)
def revalidate_registration_cmd(
    registration_id: str = typer.Argument(..., help=REGISTRATION_ID_HELP),
    db_path: str | None = typer.Option(
        None,
        "--db-path",
        help=_DB_PATH_HELP,
    ),
) -> None:
    try:
        store = build_registration_store(db_path)
        registration = revalidate_registration_record(
            registration_id=registration_id,
            store=store,
        )
    except (ValueError, OSError, typer.BadParameter) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    _print_registration_result(
        registration_id=registration.registration_id,
        adapter_name=registration.adapter_name,
        status=registration.status.value,
        profile_version=registration.profile_version,
        metadata_path=registration.metadata_path,
        validation_errors=registration.validation_errors,
    )
    if registration.status.value == "INVALID":
        console.print(
            "[red]Registration revalidation finished with validation errors[/red]"
        )
        raise typer.Exit(code=1)
    console.print("[green]Registration revalidated[/green]")


@app.command(
    "list-registrations",
    help="List active stored registrations from the configured database.",
)
def list_registrations_cmd(
    db_path: str | None = typer.Option(
        None,
        "--db-path",
        help=_DB_PATH_HELP,
    ),
) -> None:
    try:
        store = build_registration_store(db_path)
        registrations = [
            (
                registration,
                store.get_latest_event_type(registration.registration_id)
                or "SUBMITTED",
            )
            for registration in store.list_active_registrations()
        ]
    except (ValueError, OSError, typer.BadParameter) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    _print_registration_table(registrations)


@app.command(
    "show-registration-events",
    help="Show event history for one stored registration.",
)
def show_registration_events_cmd(
    registration_id: str = typer.Argument(..., help=REGISTRATION_ID_HELP),
    db_path: str | None = typer.Option(
        None,
        "--db-path",
        help=_DB_PATH_HELP,
    ),
) -> None:
    try:
        store = build_registration_store(db_path)
        if store.get_registration(registration_id) is None:
            raise ValueError(f"Registration not found: {registration_id}")
        events = store.list_registration_events(registration_id)
    except (ValueError, OSError, typer.BadParameter) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    _print_registration_events(events)


@app.command(
    "seed-demo-adapters",
    help="Insert three fake valid adapters for local catalog development.",
)
def seed_demo_adapters_cmd(
    db_path: str | None = typer.Option(
        None,
        "--db-path",
        help=_DB_PATH_HELP,
    ),
) -> None:
    try:
        store = build_registration_store(db_path)
        existing_keys = {
            entry.uniqueness_key for entry in store.list_registry_entries()
        }
        seeded = 0
        skipped = 0
        for spec in _DEMO_ADAPTERS:
            uniqueness_key = f"{spec['adapter_id']}::{spec['version']}"
            if uniqueness_key in existing_keys:
                skipped += 1
                continue
            registration = submit_registration_record(
                adapter_name=str(spec["adapter_name"]),
                repository_location=str(spec["repository_location"]),
                store=store,
                doi=spec.get("doi"),
                submitted_by_github_login=_DEMO_GITHUB_LOGIN,
            )
            store.mark_registration_valid(
                registration_id=registration.registration_id,
                metadata=_demo_adapter_metadata(spec),
                metadata_path=METADATA_FILENAME,
                profile_version="demo-v1",
                uniqueness_key=uniqueness_key,
                observed_checksum=f"demo-{uniqueness_key}",
            )
            existing_keys.add(uniqueness_key)
            seeded += 1
    except (ValueError, OSError, typer.BadParameter) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(
        f"[green]Seeded {seeded} demo adapters[/green] "
        f"([yellow]skipped {skipped} existing[/yellow])"
    )


@app.command(
    "list-registry-entries",
    help="List active canonical registry entries from the configured database.",
)
def list_registry_entries_cmd(
    db_path: str | None = typer.Option(
        None,
        "--db-path",
        help=_DB_PATH_HELP,
    ),
) -> None:
    try:
        store = build_registration_store(db_path)
        entries = store.list_registry_entries()
    except (ValueError, OSError, typer.BadParameter) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    _print_registry_entries(entries)


@app.command(
    "show-latest-refresh",
    help="Show the latest persisted registry batch refresh summary.",
)
def show_latest_refresh_cmd(
    db_path: str | None = typer.Option(
        None,
        "--db-path",
        help=_DB_PATH_HELP,
    ),
) -> None:
    try:
        store = build_registration_store(db_path)
        refresh = store.get_latest_batch_refresh()
        if refresh is None:
            raise ValueError("No registry refresh has been recorded.")
    except (ValueError, OSError, typer.BadParameter) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    _print_latest_batch_refresh(refresh)


@app.command(
    "discover",
    help=(
        "Discover exactly one adapter croissant.jsonld from a local repository path "
        "or GitHub repository URL and continue to validation."
    ),
)
def discover_cmd(
    source: str = typer.Argument(
        ...,
        help="Local repository path or GitHub repository URL.",
    ),
) -> None:
    try:
        source_scheme = urlparse(source).scheme
        if source_scheme == HTTPS_SCHEME:
            discovered = discover_remote_adapter(source)
            location_kind = "remote repository"
        elif source_scheme == HTTP_SCHEME:
            raise typer.BadParameter(
                "Only HTTPS repository URLs are supported for remote discovery."
            )
        elif source_scheme:
            raise typer.BadParameter("Unsupported repository URL scheme.")
        else:
            discovered = discover_local_adapter(source)
            location_kind = "local repository"
        discovered = validate_discovered_adapter(discovered)
    except (ValueError, OSError, typer.BadParameter) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    _print_discovery_target(
        source=source,
        metadata_path=str(discovered.metadata_path)
        if discovered.metadata_path
        else None,
        location_kind=location_kind,
    )
    console.print("[green]Discovery succeeded[/green]")

    if discovered.validation is None:
        raise typer.Exit(code=1)

    _print_validation_result(
        discovered.validation,
        "adapter",
    )


@app.command(
    "validate",
    help=("Validate a Croissant file with automatic type detection."),
)
def validate_cmd(
    path: str = typer.Argument(
        ...,
        help=("Path to a JSON-LD file or a repository containing one metadata file."),
    ),
) -> None:
    _validate_path(path)


@app.command(
    "validate-adapter",
    help=("Validate input as adapter metadata."),
)
def validate_adapter_cmd(
    path: str = typer.Argument(
        ...,
        help=("Path to adapter metadata or a repository containing it."),
    ),
) -> None:
    _validate_path(path, kind="adapter")


@app.command(
    "validate-dataset",
    help=("Validate input as dataset metadata."),
)
def validate_dataset_cmd(
    path: str = typer.Argument(
        ...,
        help=("Path to dataset metadata or a repository containing it."),
    ),
) -> None:
    _validate_path(path, kind="dataset")


@app.command("web", help="Launch the web interface.")
def web_cmd(
    host: str = typer.Option("127.0.0.1", help="Host to bind."),
    port: int = typer.Option(8000, help="Port to bind."),
    output_dir: str = typer.Option(".", help="Directory for generated files."),
) -> None:
    from src.core.web.server import run_server

    console.print(f"[cyan]Serving web UI on http://{host}:{port}[/cyan]")
    run_server(host=host, port=port, output_dir=output_dir)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
