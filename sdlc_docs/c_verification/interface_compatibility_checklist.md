# Interface Compatibility Checklist

## Purpose

This checklist tracks whether the FastAPI API and CLI deliver the same
project behavior through shared core services. Registration UI references now
refer to React; metadata-generation design references retain their original scope.

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

Registration UI
  frontend/src/pages/RegisterPage.tsx
  frontend/src/pages/AdaptersPage.tsx
```

The original metadata/legacy-web inventory below remains design context.
Registration uses the React/API boundary and shared service contract described here.

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

| Capability | API | CLI | UI / Baseline Reference | Shared Core Boundary | Current Status |
| --- | --- | --- | --- | --- | --- |
| Health check | `GET /api/v1/health` | None | None | API-only | Compatible, API-only |
| Create registration | `POST /api/v1/registrations` or `/registrations/stream` | `register` | Registration form | `register_adapter` | Atomic acceptance, verified owner |
| Owned update | `POST /api/v1/adapters/{adapter_id}/update` | `update` | Adapter Update action | `update_adapter` | Shared ownership and acceptance rules |
| Batch refresh | No HTTP mutation route | `refresh-registry` | No browser trigger | `refresh_active_registrations` | Trusted maintenance operation |
| Latest refresh summary | `GET /api/v1/registry/refreshes/latest` | `show-latest-refresh` | `GET /registry` summary panel | `RegistrationStore.get_latest_batch_refresh` | Compatible |
| List registrations | `GET /api/v1/registrations` and `GET /api/v1/registry/registrations` | `list-registrations` | `GET /registry` | `RegistrationStore.list_active_registrations` | Mostly compatible |
| Registration detail | `GET /api/v1/registrations/{id}` | No direct detail command | `GET /register?registration_id=...` | `RegistrationStore.get_registration` | Partial CLI gap |
| Registration events | `GET /api/v1/registrations/{id}/events` | `show-registration-events` | registration detail page | `RegistrationStore.list_registration_events` | Compatible |
| Registry entries | `GET /api/v1/registry/entries` | `list-registry-entries` | registration detail current entry block | `RegistrationStore.list_registry_entries` | Partial web gap |
| Registry entry detail | `GET /api/v1/registry/entries/{entry_id}` | No direct command | registration detail current entry block | `RegistrationStore.get_registry_entry` | Partial CLI gap |
| Public adapter catalog | `GET /api/v1/adapters` | Removed old aggregated-file `list` command | React adapter page | `RegistrationStore.list_registry_entries` | Implemented in API/UI; CLI gap |
| Public adapter detail | `GET /api/v1/adapters/{adapter_id}` | Removed old aggregated-file `inspect` command | React adapter detail modal | `RegistrationStore.list_registry_entries` | Implemented in API/UI; CLI gap |
| Public adapter metadata | `GET /api/v1/adapters/{adapter_id}/metadata` | Removed old aggregated-file `inspect` command | React adapter detail modal | `RegistrationStore.list_registry_entries` | Implemented in API/UI; CLI gap |
| Metadata validation | `POST /api/v1/metadata/validate` | `validate`, `validate-adapter`, `validate-dataset` | generation result validation only | `validate_adapter_with_embedded_datasets`, `validate_dataset` | Mostly compatible |
| Dataset metadata generation | `POST /api/v1/metadata/datasets/generate` | `dataset direct/config/guided` | Create-metadata workflow | `src.core.dataset.service.execute_request` | Shared generation; transport differs |
| Browser dataset generation | Upload-session create/upload/finalize/status/delete routes | None | Create-metadata file/folder selection | `UploadSessionManager` + dataset service | Browser-specific transport over shared generation |
| Adapter metadata generation | `POST /api/v1/metadata/adapters/generate` | `adapter direct/config/guided` | metadata generation form | `src.core.adapter.service.execute_request` | Compatible with duplicated mapping |

## Current Findings

### Healthy Areas

- First registration, owned adapter updates and manual batch refresh call shared
  core services. Failed first attempts leave no records; failed updates preserve
  accepted metadata and append terminal history.
- Browser publication uses its existing session. CLI publication verifies a
  GitHub device-flow identity, revokes its temporary token and calls services
  directly against the same configured database.
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
- API and CLI store construction goes through
  `src/persistence/factory.py`.
- CLI registry commands can use `SQLITE_DATABASE_PATH` when `--db-path` is
  not supplied.
- The old aggregated-file CLI commands `list`, `inspect`, and `export` were
  removed to avoid presenting `unified_adapters_metadata.jsonld` as the current
  registry source of truth.

### Remaining Gaps And Duplication

- Registry overview presentation remains separate between API models and CLI
  table formatting; accepted state and latest attempts must stay consistent.
- Public catalog grouping remains in API routes; canonical identity and latest
  entry selection are shared through `src/core/adapter/catalog.py`.
- Metadata generation request mapping exists separately in API schemas/routes,
  CLI parsing, YAML config readers, and React form normalization.
- API has dedicated public adapter catalog endpoints consumed by the React
  adapter page. CLI does not yet expose equivalent registry-backed catalog
  operations.

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
- Keep React workflow mapping in frontend modules and move only reusable
  generation behavior into core helpers; do not couple core to browser types.

### Later

- Keep SQLite/PostgreSQL parity through the shared registration store port
  and tests against the disposable PostgreSQL environment.
- Keep the generated frontend client synchronized with FastAPI OpenAPI and
  retain contract coverage for the browser upload workflow.
- Decide whether public adapter catalog operations should become first-class
  CLI commands.

## Suggested Next Implementation Step

Verify registration changes through shared service, API and CLI scenarios:

1. Accept a valid first candidate atomically; reject invalid metadata without
   source, entry or event rows, then retry successfully with the same version.
2. Reject duplicate repositories/identity-version keys and conflicting owners,
   including concurrent writes and normalized repository aliases.
3. Preserve accepted metadata on failed updates; require identity preservation
   and a different unused label for changed candidates.
4. Check streamed progress, diagnostics/schema provenance and unconfirmed
   disconnect behavior without automatic resubmission.
5. Verify CLI device authorization/revocation, shared database selection and
   per-source isolation with separate fetch/internal batch counters.

```bash
docker compose -f docker-compose.test.yml up -d --wait database
REGISTRY_TEST_POSTGRES_CONTAINER=biocypher-registry-test-database uv run pytest -ra
docker compose -f docker-compose.test.yml down
```

SQLite tests run without Docker. PostgreSQL cases use the labeled disposable
container and isolated schemas; unavailable infrastructure skips only those
cases. Database configuration errors and test failures remain errors.

Further read-model consolidation can follow the existing short/medium-term
checklist. Agentic workspace behavior has a separate contract and is outside
this registration change.
