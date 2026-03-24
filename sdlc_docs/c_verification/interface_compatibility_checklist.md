# Interface Compatibility Checklist

## Purpose

This checklist tracks whether the FastAPI API, CLI, and temporary legacy web UI
deliver the same project behavior through shared core services.

The goal is not for every interface to expose every operation. The goal is that
when two interfaces expose the same operation, they call the same core contract
and preserve the same defaults, validation rules, persistence behavior, and
status transitions.

## Interfaces In Scope

```text
FastAPI API
  src/api

CLI
  cli.py
  src/core/dataset/cli.py
  src/core/adapter/cli.py

Legacy web UI
  src/core/web
```

`src/core/web` is temporary. New reusable behavior should be moved into core
services or query helpers before the future frontend consumes it.

## Compatibility Principles

- Delivery layers should translate interface-specific input into core request
  models or service calls.
- Business behavior belongs in `src/core`, not in API routes, Typer commands,
  or web request handlers.
- Persistence implementations belong in `src/persistence`.
- Full Croissant metadata should be returned by detail or dedicated metadata
  reads, not by list/table endpoints.
- Metadata generation validates by default unless the user explicitly opts out.
- The web-only `confirm_croissant_root` checkbox remains a UI confirmation. It
  is not stored in the core model, database, API contract, or CLI contract.

## Compatibility Matrix

| Capability | API | CLI | Legacy Web UI | Shared Core Boundary | Current Status |
| --- | --- | --- | --- | --- | --- |
| Health check | `GET /api/v1/health` | None | None | API-only | Compatible, API-only |
| Create registration | `POST /api/v1/registrations` | `submit-registration` | `POST /register` | `submit_registration` | Compatible |
| Process registration | `POST /api/v1/registrations/{id}/process` | `finish-registration` | `POST /register/process` | `finish_registration` | Compatible |
| Revalidate registration | `POST /api/v1/registrations/{id}/revalidate` | `revalidate-registration` | `POST /register/revalidate` | `revalidate_registration` | Compatible |
| Batch refresh | `POST /api/v1/registry/refreshes` | `refresh-registry` | `POST /registry/refresh` | `refresh_active_registrations` | Compatible |
| Latest refresh summary | `GET /api/v1/registry/refreshes/latest` | `show-latest-refresh` | `GET /registry` summary panel | `RegistrationStore.get_latest_batch_refresh` | Compatible |
| List registrations | `GET /api/v1/registrations` and `GET /api/v1/registry/registrations` | `list-registrations` | `GET /registry` | `RegistrationStore.list_active_registrations` | Mostly compatible |
| Registration detail | `GET /api/v1/registrations/{id}` | No direct detail command | `GET /register?registration_id=...` | `RegistrationStore.get_registration` | Partial CLI gap |
| Registration events | `GET /api/v1/registrations/{id}/events` | `show-registration-events` | registration detail page | `RegistrationStore.list_registration_events` | Compatible |
| Registry entries | `GET /api/v1/registry/entries` | `list-registry-entries` | registration detail current entry block | `RegistrationStore.list_registry_entries` | Partial web gap |
| Registry entry detail | `GET /api/v1/registry/entries/{entry_id}` | No direct command | registration detail current entry block | `RegistrationStore.get_registry_entry` | Partial CLI gap |
| Public adapter catalog | `GET /api/v1/adapters` | Removed old aggregated-file `list` command | Future frontend only | `RegistrationStore.list_registry_entries` | CLI gap |
| Public adapter detail | `GET /api/v1/adapters/{adapter_id}` | Removed old aggregated-file `inspect` command | Future frontend only | `RegistrationStore.list_registry_entries` | CLI gap |
| Public adapter metadata | `GET /api/v1/adapters/{adapter_id}/versions/{version}/metadata` | Removed old aggregated-file `inspect` command | Future frontend only | `RegistrationStore.list_registry_entries` | CLI gap |
| Metadata validation | `POST /api/v1/metadata/validate` | `validate`, `validate-adapter`, `validate-dataset` | generation result validation only | `validate_adapter_with_embedded_datasets`, `validate_dataset` | Mostly compatible |
| Dataset metadata generation | `POST /api/v1/metadata/datasets/generate` | `dataset direct/config/guided` | No standalone dataset route | `src.core.dataset.service.execute_request` | Partial web gap |
| Adapter metadata generation | `POST /api/v1/metadata/adapters/generate` | `adapter direct/config/guided` | metadata generation form | `src.core.adapter.service.execute_request` | Compatible with duplicated mapping |

## Current Findings

### Healthy Areas

- Registration submission, processing, revalidation, and batch refresh already
  call shared core services from all relevant interfaces.
- Adapter registration validation uses the shared registry-level validation
  contract, including embedded dataset validation.
- API and CLI metadata validation both resolve adapter and dataset validation
  through the shared validation modules.
- Metadata generation defaults to validation enabled across core request
  objects, CLI commands, API request schemas, config readers, and the web form.
- Full metadata is intentionally absent from list/table endpoints and available
  through detail or dedicated metadata endpoints.

### Resolved In Current Cleanup

- Database path wiring is centralized in `src/core/settings.py`.
- API, CLI, and legacy web store construction now goes through
  `src/persistence/factory.py`.
- CLI registry commands can use `BIOCYPHER_REGISTRY_DB_PATH` when `--db-path` is
  not supplied.
- The old aggregated-file CLI commands `list`, `inspect`, and `export` were
  removed to avoid presenting `unified_adapters_metadata.jsonld` as the current
  registry source of truth.

### Remaining Gaps And Duplication

- Registry overview rows are assembled separately in API routes, CLI table
  formatting, and legacy web helpers.
- Adapter catalog grouping is implemented in the API route only.
- Metadata generation request mapping exists separately in API schemas/routes,
  CLI parsing, YAML config readers, and legacy web form normalization.
- API has dedicated public adapter catalog endpoints. CLI and legacy web UI do
  not yet expose equivalent registry-backed catalog operations.

## Refactoring Checklist

### Short Term

- Add core query helpers for common read models:
  - list registration overview rows
  - get registration detail with current registry entry
  - list canonical registry entries
  - get latest refresh summary
  - list public adapter catalog entries
  - get public adapter version metadata
- Replace API-only adapter catalog grouping with a reusable core query helper.
- Add registry-backed CLI commands for public adapter catalog reads only after
  the reusable core query helper exists.

### Medium Term

- Move repeated metadata generation request mapping into shared factory helpers
  where it does not leak HTTP, Typer, or HTML concerns into core.
- Add compatibility tests that compare API responses with the equivalent core
  or CLI-visible behavior for key workflows.
- Keep the legacy web UI as a thin caller of shared core/query functions until
  the React frontend replaces it.

### Later

- Introduce PostgreSQL by implementing the same registration store/query ports
  already used by SQLite.
- Add frontend contract tests against the FastAPI OpenAPI schema once the React
  frontend starts consuming the API.
- Decide whether public adapter catalog operations should become first-class
  CLI commands.

## Suggested Next Implementation Step

Start with configuration and store construction:

```text
src/core/config.py or src/core/settings.py
  shared registry database path setting

src/persistence/factory.py
  build_registration_store(database_path: Path | str | None = None)
```

Then update API dependencies, CLI commands, and legacy web helpers to use the
same store construction path. This is a small change with a useful payoff: it
removes duplicated database wiring before deeper read-model refactoring.
