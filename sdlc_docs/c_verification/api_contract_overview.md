# API Contract Overview

This document summarizes the current FastAPI contract and how each API group
maps to the core services, CLI commands, and registration UI. It is a companion
to the manual HTTPie checklist in `api_manual_verification.md` and the
interface compatibility checklist in `interface_compatibility_checklist.md`.

## Assumptions

- Local API base URL: `http://127.0.0.1:8000`
- API prefix: `/api/v1`
- Default registry database: `registry.sqlite3`
- The FastAPI API and CLI share registration behavior; React calls the API.
- The API owns JSON contracts only. It should not own validation, duplicate
  detection, checksums, status transitions, or persistence rules.

## Contract Groups

| Group | Endpoint Family | Purpose | Stateful | Primary Core Boundary |
| --- | --- | --- | --- | --- |
| Health | `/health` | Confirm the API process is alive. | No | API-only status response |
| Authentication | `/auth/...` | Read or end the browser's GitHub-backed session. | Yes | Auth service and `AuthSessionStore` |
| Registrations | `/registrations` | Validate and accept a repository once, stream progress, and inspect accepted sources/history. | Yes | `src.core.registration.service` and `RegistrationStore` |
| Registry operations | `/registry/...` | Read published sources, completed batch summaries and canonical entries. | Yes | `RegistrationStore` and batch refresh service |
| Adapter catalog | `/adapters` | Public read model built from valid canonical registry entries. | Yes, read-only | `RegistrationStore.list_registry_entries` |
| Metadata utilities | `/metadata/...` | Validate or generate metadata without persisting a registration. | No | Dataset, adapter, and validation core services |
| Dataset upload sessions | `/metadata/upload-sessions/...` | Ephemeral browser artifact upload, queued generation, polling, and cleanup. | Process-local only | `UploadSessionManager` and dataset generation services |

## Endpoint Map

| Endpoint | Purpose | CLI Equivalent | UI / Baseline Reference |
| --- | --- | --- | --- |
| `GET /api/v1/health` | API liveness check. | None | None |
| `GET /api/v1/auth/me` | Read the signed-in GitHub identity. | None | Application header/session state |
| `POST /api/v1/auth/logout` | Delete the local browser session. | None | Sign-out action |
| `POST /api/v1/registrations` | Authenticate, validate and atomically accept a first repository. | `register` | Current registration UI |
| `POST /api/v1/registrations/stream` | Same registration with live check events and one terminal result. | `register` check output | Current registration UI |
| `POST /api/v1/adapters/{adapter_id}/update` | Update a published adapter as its owner. | `update` | Published adapter Update action |
| `GET /api/v1/schemas/{version}` | Exact deployed adapter schema. | Bundled profile loader | Registration schema viewer |
| `GET /api/v1/registrations` | List active registrations as summary rows. | `list-registrations` | `GET /registry` |
| `GET /api/v1/registrations/{registration_id}` | Inspect one registration, including processing details. | None direct | registration detail page |
| `GET /api/v1/registrations/{registration_id}/events` | Inspect processing event history for one registration. | `show-registration-events` | registration detail page |
| `GET /api/v1/registry/registrations` | Published versions/latest attempts with latest-event filtering. | `list-registrations` | `GET /registry` |
| `GET /api/v1/registry/refreshes/latest` | Read the latest persisted batch refresh summary. | `show-latest-refresh` | `GET /registry` summary panel |
| `GET /api/v1/registry/entries` | List canonical valid registry entries. | `list-registry-entries` | registration detail current entry block |
| `GET /api/v1/registry/entries/{entry_id}` | Read one canonical valid registry entry. | None direct | registration detail current entry block |
| `GET /api/v1/adapters` | List public adapter catalog items. | No direct command | React adapter catalog |
| `GET /api/v1/adapters/latest` | List the latest public adapter cards. | None | React adapter page |
| `GET /api/v1/adapters/search` | Search public adapter cards. | None | React adapter search |
| `GET /api/v1/adapters/{adapter_id}` | Read one adapter with registered versions. | No direct command | React adapter detail |
| `DELETE /api/v1/adapters/{adapter_id}` | Delete an adapter as its owner. | None | React adapter delete action |
| `POST /api/v1/adapters/{adapter_id}/endorse` | Endorse an adapter as the signed-in user. | None | React adapter endorsement action |
| `GET /api/v1/adapters/{adapter_id}/metadata` | Read the latest accepted Croissant metadata for an adapter. | No direct command | React adapter detail |
| `POST /api/v1/metadata/validate` | Validate inline adapter or dataset metadata without storing it. | `validate`, `validate-adapter`, `validate-dataset` | metadata generation result validation |
| `POST /api/v1/metadata/datasets/generate` | Generate dataset metadata from one multipart file upload. | `dataset direct`, `dataset config`, `dataset guided` | Standalone API; React file/folder generation uses upload sessions |
| `POST /api/v1/metadata/upload-sessions` | Declare a browser-prepared file/folder inventory and reserve capacity. | None | dataset source selection |
| `PUT /api/v1/metadata/upload-sessions/{session_id}/artifacts/{entry_id}` | Stream and verify one bounded artifact. | None | dataset upload progress |
| `POST /api/v1/metadata/upload-sessions/{session_id}/finalize` | Queue generation and return `202`. | None | dataset generation progress |
| `GET /api/v1/metadata/upload-sessions/{session_id}` | Poll state and retrieve a terminal result. | None | dataset generation progress/result |
| `DELETE /api/v1/metadata/upload-sessions/{session_id}` | Cancel before finalization or release a consumed session. | None | dataset generation cleanup |
| `POST /api/v1/metadata/adapters/generate` | Generate adapter metadata from existing or generated datasets. | `adapter direct`, `adapter config`, `adapter guided` | metadata generation form |

## Compatibility Rules

- Registration, owned updates and trusted CLI batch refresh call shared core
  services. Failed first attempts create no records; failed published updates
  preserve accepted metadata and append terminal history.
- Browser publication uses its GitHub session; CLI publication verifies identity
  and revokes its temporary device-flow token before calling services directly.
- An SSE terminal result follows persistence. Never automatically repeat a
  disconnected registration POST.
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
| `/auth/me`, `/auth/logout` | Session state only | Read or delete the local authenticated browser session. |
| `/metadata/validate` | No | Validates an inline document only. |
| `/metadata/*/generate` | No registry persistence | Uses temporary server-side files and returns generated metadata. |
| `/metadata/upload-sessions` | No registry persistence | Process-local state and tmpfs artifacts; scratch is deleted at terminal completion. |
| `/registrations` | Accepted candidates only | Atomic first acceptance; rejected first attempts create no records. |
| `/registry/refreshes/latest` | Read-only | Returns the last completed CLI batch summary. |
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

- First registration validates and accepts in one operation. JSON acceptance is
  `201`; candidate rejection is a terminal `FAILED` result with no records.
- `/registrations/{id}/process`, `/registrations/{id}/revalidate` and HTTP batch
  mutation routes are removed. Use registration retry, owned Update and CLI
  `refresh-registry` respectively.
- Read models separate `published_version` from `latest_attempt`. There is no
  registration lifecycle `status` field/filter. `latest_event` supports strict
  values; invalid values return `422`.
- Batch summaries persist timestamps/IDs and distinguish `fetch_failed` from
  `internal_failed`. Automatic scheduling and retry backoff remain future work.
- The old scripts pipeline remains retired. Registry automation uses shared
  services through maintained delivery adapters.

The endpoint map retains the original metadata-utility references. Exact schemas
remain in runtime OpenAPI; the agentic workspace keeps its separate
[/agent/api/v1 contract](../../docs/API.md).
