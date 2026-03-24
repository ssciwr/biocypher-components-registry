# API Contract Overview

This document summarizes the current FastAPI contract and how each API group
maps to the core services, CLI commands, and legacy web UI. It is a companion
to the manual HTTPie checklist in `api_manual_verification.md` and the
interface compatibility checklist in `interface_compatibility_checklist.md`.

## Assumptions

- Local API base URL: `http://127.0.0.1:8000`
- API prefix: `/api/v1`
- Default registry database: `registry.sqlite3`
- The FastAPI API, CLI, and legacy web UI must share core business behavior.
- The API owns JSON contracts only. It should not own validation, duplicate
  detection, checksums, status transitions, or persistence rules.

## Contract Groups

| Group | Endpoint Family | Purpose | Stateful | Primary Core Boundary |
| --- | --- | --- | --- | --- |
| Health | `/health` | Confirm the API process is alive. | No | API-only status response |
| Registrations | `/registrations` | Submit, process, inspect, and revalidate repository registrations. | Yes | `src.core.registration.service` and `RegistrationStore` |
| Registry operations | `/registry/...` | Operator view of active registrations, batch refreshes, and canonical entries. | Yes | `RegistrationStore` and batch refresh service |
| Adapter catalog | `/adapters` | Public read model built from valid canonical registry entries. | Yes, read-only | `RegistrationStore.list_registry_entries` |
| Metadata utilities | `/metadata/...` | Validate or generate metadata without persisting a registration. | No | Dataset, adapter, and validation core services |

## Endpoint Map

| Endpoint | Purpose | CLI Equivalent | Legacy Web UI Equivalent |
| --- | --- | --- | --- |
| `GET /api/v1/health` | API liveness check. | None | None |
| `POST /api/v1/registrations` | Store one submitted adapter repository. | `submit-registration` | `POST /register` |
| `GET /api/v1/registrations` | List active registrations as summary rows. | `list-registrations` | `GET /registry` |
| `GET /api/v1/registrations/{registration_id}` | Inspect one registration, including processing details. | None direct | registration detail page |
| `GET /api/v1/registrations/{registration_id}/events` | Inspect processing event history for one registration. | `show-registration-events` | registration detail page |
| `POST /api/v1/registrations/{registration_id}/process` | Discover and validate one submitted registration. | `finish-registration` | `POST /register/process` |
| `POST /api/v1/registrations/{registration_id}/revalidate` | Reprocess one `INVALID` or `FETCH_FAILED` registration. | `revalidate-registration` | `POST /register/revalidate` |
| `GET /api/v1/registry/registrations` | Operator list with status and latest event filtering. | `list-registrations` | `GET /registry` |
| `POST /api/v1/registry/refreshes` | Process all active registrations once. | `refresh-registry` | `POST /registry/refresh` |
| `GET /api/v1/registry/refreshes/latest` | Read the latest persisted batch refresh summary. | `show-latest-refresh` | `GET /registry` summary panel |
| `GET /api/v1/registry/entries` | List canonical valid registry entries. | `list-registry-entries` | registration detail current entry block |
| `GET /api/v1/registry/entries/{entry_id}` | Read one canonical valid registry entry. | None direct | registration detail current entry block |
| `GET /api/v1/adapters` | List public adapter catalog items. | Future registry-backed adapter list | Future frontend catalog |
| `GET /api/v1/adapters/{adapter_id}` | Read one adapter with registered versions. | Future registry-backed adapter detail | Future frontend catalog |
| `GET /api/v1/adapters/{adapter_id}/versions/{version}/metadata` | Read full Croissant metadata for one canonical adapter version. | Future registry-backed metadata read | Future frontend catalog |
| `POST /api/v1/metadata/validate` | Validate inline adapter or dataset metadata without storing it. | `validate`, `validate-adapter`, `validate-dataset` | metadata generation result validation |
| `POST /api/v1/metadata/datasets/generate` | Generate dataset metadata from server-side input files. | `dataset direct`, `dataset config`, `dataset guided` | metadata generation form |
| `POST /api/v1/metadata/adapters/generate` | Generate adapter metadata from existing or generated datasets. | `adapter direct`, `adapter config`, `adapter guided` | metadata generation form |

## Compatibility Rules

- Registration submission, processing, revalidation, and batch refresh must call
  shared core registration services.
- Registry reads must use `RegistrationStore` methods or future query ports.
- Metadata generation validates by default across FastAPI, CLI, config, web,
  and core request objects. Interfaces may expose explicit opt-out controls.
- Adapter validation uses the registry-level validation contract:
  adapter compliance/schema/semantics plus every embedded dataset fragment.
- `confirm_croissant_root` belongs only to the web UI. It is not an API or core
  field.
- Full Croissant metadata should not appear in list endpoints. Use detail or
  dedicated metadata endpoints when full documents are needed.

## Stateful vs Stateless Endpoints

| Endpoint Family | Persists Data | Notes |
| --- | --- | --- |
| `/health` | No | Lightweight liveness response. |
| `/metadata/validate` | No | Validates an inline document only. |
| `/metadata/*/generate` | No registry persistence | Uses temporary server-side files and returns generated metadata. |
| `/registrations` | Yes | Creates and updates registration records and events. |
| `/registry/refreshes` | Yes | Records batch refresh summaries and registration outcomes. |
| `/registry/entries` | Read-only | Reads canonical valid entries. |
| `/adapters` | Read-only | Public projection from canonical valid entries. |

## Versioning

The API uses path-based major versioning:

```text
/api/v1
```

The OpenAPI application version remains the project/application version. The
path prefix represents the public HTTP contract generation. Minor compatible
changes stay under `/api/v1`; breaking changes should move to `/api/v2`.

## Current Decisions

- `POST /api/v1/registry/refreshes` is the only API route for starting a batch
  refresh. The previous singular refresh route is not kept as an API alias.
- `GET /api/v1/registry/registrations` accepts strict `status` and
  `latest_event` filter values. Unsupported values return `422`.
- The old `scripts/` registry pipeline is retired. Registry automation should
  use the shared CLI/API/core workflow.
