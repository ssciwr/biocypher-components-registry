from __future__ import annotations

import hashlib
import json
import os
import webbrowser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.core.adapter.cli import app as adapter_app
from src.core.adapter.discovery import (
    discover_local_adapter,
    discover_remote_adapter,
    validate_discovered_adapter,
)
from src.core.adapter.service import create_registration_request
from src.core.auth.service import GitHubAuthenticationError, authenticate_github_device
from src.core.dataset.cli import app as dataset_app
from src.core.registration.models import (
    AttemptStatus,
    BatchRefreshRecord,
    ProcessingOutcome,
    RegistrationEvent,
    RegistryEntry,
    StoredRegistration,
)
from src.core.registration.service import (
    refresh_active_registrations as refresh_active_registrations_record,
)
from src.core.registration.service import register_adapter, update_adapter
from src.core.settings import settings as core_settings
from src.core.shared.constants import (
    CROISSANT_CONFORMS_TO_URL,
    METADATA_FILENAME,
    STANDARD_CONTEXT,
)
from src.core.shared.files import fetch_local_metadata, parse_json_metadata
from src.core.validation import (
    validate_adapter_with_embedded_datasets,
    validate_dataset,
)
from src.core.validation.results import ValidationResult
from src.persistence.errors import DatabaseSetupError
from src.persistence.factory import build_registration_store, check_database_connection

# ============================================================================
# Constants
# ============================================================================

STYLE_SECTION_HEADING = "bold cyan"
ADAPTER_LABEL = "Adapter\n"
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
    pretty_exceptions_show_locals=False,
)
console = Console()
app.add_typer(dataset_app, name="dataset")
app.add_typer(adapter_app, name="adapter")


def _demo_adapter_metadata(spec: dict[str, Any]) -> dict[str, Any]:
    adapter_id = str(spec["adapter_id"])
    data_source = str(spec["data_source"])
    return {
        "@context": STANDARD_CONTEXT,
        JSONLD_TYPE: "SoftwareSourceCode",
        "@id": adapter_id,
        "name": spec["adapter_name"],
        "description": spec["description"],
        "version": spec["version"],
        "license": "MIT",
        "codeRepository": spec["repository_location"],
        "programmingLanguage": "Python",
        "targetProduct": "BioCypher",
        "creator": [{JSONLD_TYPE: "Person", "name": "BioCypher demo user"}],
        "keywords": spec["keywords"],
        "hasPart": [
            {
                JSONLD_TYPE: "sc:Dataset",
                "name": data_source,
                "conformsTo": CROISSANT_CONFORMS_TO_URL,
                "citeAs": f"https://example.org/{adapter_id}",
                "datePublished": "2026-01-01T00:00:00",
                "creator": [{JSONLD_TYPE: "sc:Person", "name": "BioCypher demo user"}],
                "description": f"Vague demo dataset backing the {spec['adapter_name']}.",
                "version": "2026.1",
                "license": "MIT",
                "url": f"https://example.org/{adapter_id}",
                "distribution": [
                    {
                        "@id": f"{adapter_id}-data",
                        JSONLD_TYPE: "cr:FileObject",
                        "name": "demo.csv",
                        "contentUrl": f"https://example.org/{adapter_id}/demo.csv",
                        "encodingFormat": "text/csv",
                        "sha256": hashlib.sha256(b"source,target,score\n").hexdigest(),
                    }
                ],
                "recordSet": [
                    {
                        JSONLD_TYPE: "cr:RecordSet",
                        "@id": f"{adapter_id}-records",
                        "name": "records",
                        "field": [
                            {
                                "@id": f"{adapter_id}-records/{name}",
                                JSONLD_TYPE: "cr:Field",
                                "name": name,
                                "description": f"Demo {name} value",
                                "dataType": "sc:Float"
                                if name == "score"
                                else "sc:Text",
                                "source": {
                                    "fileObject": {"@id": f"{adapter_id}-data"},
                                    "extract": {"column": name},
                                },
                            }
                            for name in ("source", "target", "score")
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
    except (ValueError, OSError, typer.BadParameter, DatabaseSetupError) as exc:
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


def _print_batch_refresh_summary(
    active_sources: int,
    processed: int,
    valid_created: int,
    unchanged: int,
    invalid: int,
    duplicate: int,
    rejected_same_version_changed: int,
    fetch_failed: int,
    internal_failed: int = 0,
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
    table.add_row("INTERNAL_FAILED", str(internal_failed))
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
        internal_failed=refresh.internal_failed,
    )


def _print_registration_table(
    registrations: list[tuple[StoredRegistration, str]],
) -> None:
    """Print stored registrations in a compact table."""
    table = Table(title="Stored Registrations")
    table.add_column("Registration ID", style="cyan")
    table.add_column("Adapter")
    table.add_column("Published Version")
    table.add_column("Latest Event")
    table.add_column("Kind")
    table.add_column("Last Checked")
    for registration, latest_event in registrations:
        table.add_row(
            registration.registration_id,
            registration.adapter_name,
            str((registration.metadata or {}).get("version", "n/a")),
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


def _authorize_cli():
    client_id = os.getenv(core_settings.github_oauth_client_id_env, "").strip()
    client_secret = os.getenv(core_settings.github_oauth_client_secret_env, "").strip()
    if not client_id or not client_secret:
        raise GitHubAuthenticationError(
            "GitHub OAuth client ID and secret are required."
        )

    def present(uri: str, code: str) -> None:
        console.print(f"Open {uri} and enter code {code}", markup=False)
        try:
            webbrowser.open(uri)
        except (OSError, webbrowser.Error):
            console.print(
                "Could not open a browser. Use the verification URL and code above."
            )

    return authenticate_github_device(
        client_id=client_id, client_secret=client_secret, on_authorization=present
    )


def _print_outcome(outcome: ProcessingOutcome) -> None:
    console.print(outcome.attempt_status.value, markup=False)
    console.print(outcome.message, markup=False)
    if outcome.published_version:
        console.print(f"Published version: {outcome.published_version}", markup=False)
    if outcome.registration:
        console.print(f"Adapter: {outcome.registration.adapter_id}", markup=False)
    for error in dict.fromkeys(outcome.validation_errors):
        if error != outcome.message and not outcome.message.startswith(error):
            console.print(error, markup=False)
    if outcome.attempt_status == AttemptStatus.FAILED:
        raise typer.Exit(1)


def _authorize_for_database(db_path=None):
    try:
        console.print(f"Database: {check_database_connection(db_path)}", markup=False)
        actor = _authorize_cli()
    except (GitHubAuthenticationError, DatabaseSetupError) as exc:
        console.print(str(exc), markup=False)
        raise typer.Exit(1) from None
    except KeyboardInterrupt:
        console.print("Authentication cancelled.")
        raise typer.Exit(130) from None
    return actor


def _run_publish(operation, db_path=None) -> None:
    actor = _authorize_for_database(db_path)
    try:
        outcome = operation(actor)
    except (ValueError, PermissionError, LookupError, DatabaseSetupError) as exc:
        console.print(str(exc), markup=False)
        raise typer.Exit(1) from None
    except KeyboardInterrupt:
        console.print(
            "Operation interrupted; outcome unconfirmed. Inspect the registry before retrying."
        )
        raise typer.Exit(130) from None
    except Exception as exc:  # noqa: BLE001 - commit may have happened; redact provider details.
        console.print(
            f"Operation outcome unconfirmed ({type(exc).__name__}). "
            "Inspect the registry before retrying.",
            markup=False,
        )
        raise typer.Exit(1) from None
    _print_outcome(outcome)


@app.command(
    "register",
    help="Authenticate with GitHub and register public HTTPS repository metadata.",
)
def register_cmd(
    repository_location: str = typer.Argument(..., help="Public HTTPS repository URL."),
    db_path: str | None = typer.Option(None, "--db-path", help=_DB_PATH_HELP),
    license_value: str | None = typer.Option(None, "--license", "--license-value"),
    doi: str | None = typer.Option(None, "--doi"),
    cff_url: str | None = typer.Option(None, "--cff-url"),
) -> None:
    parsed = urlparse(repository_location)
    if parsed.scheme != "https" or not parsed.netloc:
        raise typer.BadParameter("Registration requires a public HTTPS repository URL.")
    # Normalize before authentication; malformed repository inputs must not prompt.
    try:
        request = create_registration_request(repository_location)
    except (ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from None

    def process(actor):
        return register_adapter(
            request.repository_location,
            build_registration_store(db_path),
            actor=actor,
            license_value=license_value,
            doi=doi,
            cff_url=cff_url,
            on_check=lambda check: console.print(
                f"{check.name}: {check.status}", markup=False
            ),
        )

    _run_publish(process, db_path=db_path)


@app.command(
    "update", help="Authenticate with GitHub and update an owned public adapter."
)
def update_cmd(
    adapter_id: str = typer.Argument(..., help="Public adapter ID."),
    db_path: str | None = typer.Option(None, "--db-path", help=_DB_PATH_HELP),
    force_validation: bool = typer.Option(
        False, "--force-validation", help="Validate even when metadata is unchanged."
    ),
) -> None:
    if not adapter_id.strip():
        raise typer.BadParameter("Adapter ID must not be blank.")
    _run_publish(
        lambda actor: update_adapter(
            adapter_id.strip(),
            build_registration_store(db_path),
            actor=actor,
            force_validation=force_validation,
            on_check=lambda check: console.print(
                f"{check.name}: {check.status}", markup=False
            ),
        ),
        db_path=db_path,
    )


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
    force_validation: bool = typer.Option(
        False, "--force-validation", help="Validate unchanged metadata too."
    ),
) -> None:
    try:
        store = build_registration_store(db_path)
        summary = refresh_active_registrations_record(
            store=store, force_validation=force_validation
        )
    except (ValueError, OSError, typer.BadParameter, DatabaseSetupError) as exc:
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
        internal_failed=summary.internal_failed,
    )
    console.print("[green]Batch refresh finished[/green]")


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
                or "No recorded attempt",
            )
            for registration in store.list_active_registrations()
        ]
    except (ValueError, OSError, typer.BadParameter, DatabaseSetupError) as exc:
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
    except (ValueError, OSError, typer.BadParameter, DatabaseSetupError) as exc:
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
    actor = _authorize_for_database(db_path)
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
            metadata = _demo_adapter_metadata(spec)
            validation = validate_adapter_with_embedded_datasets(metadata)
            if not validation.is_valid:
                raise ValueError(
                    "Demo metadata failed validation: " + "; ".join(validation.errors)
                )
            request = create_registration_request(
                repository_location=str(spec["repository_location"]),
                doi=spec.get("doi"),
                submitted_by_github_user_id=actor.github_user_id,
            )
            checksum = hashlib.sha256(
                json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            store.accept_candidate(
                request, metadata, validation.profile_version, uniqueness_key, checksum
            )
            existing_keys.add(uniqueness_key)
            seeded += 1
    except (ValueError, OSError, typer.BadParameter, DatabaseSetupError) as exc:
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
    except (ValueError, OSError, typer.BadParameter, DatabaseSetupError) as exc:
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
    except (ValueError, OSError, typer.BadParameter, DatabaseSetupError) as exc:
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
    except (ValueError, OSError, typer.BadParameter, DatabaseSetupError) as exc:
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


def main() -> None:
    load_dotenv()
    app()


if __name__ == "__main__":
    main()
