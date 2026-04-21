# Frontend API Contract

## Purpose

This document defines how the future React frontend should consume the current
FastAPI API.

It is a screen-by-screen contract for frontend implementation. It does not
replace the OpenAPI schema; it explains which endpoints each screen needs, what
fields the UI should rely on, and which states the frontend should handle.

The frontend should treat the backend as the source of truth for:

- metadata validation
- repository discovery
- registration status transitions
- duplicate detection
- checksum/change detection
- persistence

The frontend may perform lightweight user-experience validation, but it must not
reimplement backend business rules.

## API Base

Development API base:

```text
http://127.0.0.1:8000
```

Current API prefix:

```text
/api/v1
```

Frontend clients should centralize this value in one configuration point:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

Do not hardcode `/api/v1` across individual components.

## API Client Direction

The frontend should use dedicated API-client functions instead of raw `fetch`
calls scattered through page components.

Recommended first module shape:

```text
frontend/src/api/client.ts
frontend/src/api/registrations.ts
frontend/src/api/registry.ts
frontend/src/api/adapters.ts
frontend/src/api/metadata.ts
```

Recommended response handling:

```text
2xx
  Parse JSON and return typed data.

400
  Backend rejected a validly shaped request during processing.
  Display detail as an operation error.

404
  Requested registration, registry entry, adapter, or refresh does not exist.
  Display a not-found state.

422
  Request validation failed before operation execution.
  Map field errors to the form when possible.

5xx
  Display a generic backend failure message.
```

## Screen To Endpoint Map

| Frontend Screen | Endpoint(s) | Purpose |
| --- | --- | --- |
| Health/dev status | `GET /api/v1/health` | Confirm backend availability during development. |
| Registration form | `POST /api/v1/registrations` | Submit one adapter repository for tracking. |
| Registration detail | `GET /api/v1/registrations/{registration_id}` | Show registration status, metadata, and validation results. |
| Registration events | `GET /api/v1/registrations/{registration_id}/events` | Show event history/timeline. |
| Registration actions | `POST /api/v1/registrations/{registration_id}/process`, `POST /api/v1/registrations/{registration_id}/revalidate` | Process or revalidate one registration. |
| Registry operations | `GET /api/v1/registry/registrations`, `POST /api/v1/registry/refreshes`, `GET /api/v1/registry/refreshes/latest` | Maintainer overview and batch refresh. |
| Registry entries | `GET /api/v1/registry/entries`, `GET /api/v1/registry/entries/{entry_id}` | Maintainer canonical entry inspection. |
| Adapter catalog | `GET /api/v1/adapters` | Public list of valid adapters. |
| Adapter detail | `GET /api/v1/adapters/{adapter_id}` | Public detail for one adapter and its versions. |
| Adapter metadata | `GET /api/v1/adapters/{adapter_id}/versions/{version}/metadata` | Full Croissant metadata for one adapter version. |
| Metadata validation | `POST /api/v1/metadata/validate` | Validate inline adapter or dataset metadata. |
| Dataset metadata generation | `POST /api/v1/metadata/datasets/generate` | Generate dataset Croissant metadata from server-visible files. |
| Adapter metadata generation | `POST /api/v1/metadata/adapters/generate` | Generate adapter metadata with existing or generated datasets. |

## Shared Types

### Registration Status

The frontend should treat registration status as an enum-like string.

Known values:

```text
SUBMITTED
VALID
INVALID
FETCH_FAILED
```

UI display guidance:

```text
SUBMITTED
  Neutral or info state. Processing has not completed yet.

VALID
  Success state. A canonical registry entry may exist.

INVALID
  Warning/error state. Validation errors should be visible.

FETCH_FAILED
  Warning/error state. Repository or metadata discovery failed.
```

### Registration Event Types

Known event types currently used by registry workflows:

```text
SUBMITTED
VALID_CREATED
UNCHANGED
DUPLICATE
REJECTED_SAME_VERSION_CHANGED
INVALID_SCHEMA
INVALID_MLCROISSANT
INVALID_BOTH
FETCH_FAILED
REVALIDATED
```

Frontend event rendering should not assume this list is exhaustive. Unknown
event types should still render as text.

### Validation Result

Validation responses include:

```text
kind
is_valid
profile_version
errors
checks[]
```

Each check includes:

```text
name
is_valid
errors
```

Use `is_valid` for the summary state. Use `checks` for detailed diagnostic UI.

## Registration Form

Primary route suggestion:

```text
/registrations/new
```

Endpoint:

```text
POST /api/v1/registrations
```

Request fields:

| Field | Required | UI Control | Notes |
| --- | --- | --- | --- |
| `adapter_name` | Yes | Text input | Human-readable name. Frontend should trim before submit. |
| `repository_location` | Yes | Text input | Local server path or supported remote repository URL. |
| `contact_email` | No | Email input | Optional maintainer email. |

UI-only field:

| Field | Sent to API | Notes |
| --- | --- | --- |
| `confirm_croissant_root` | No | Checkbox reminding users that `croissant.jsonld` must be at repository root. |

Successful response fields used by UI:

```text
registration_id
adapter_name
adapter_id
repository_location
repository_kind
status
created_at
contact_email
```

Success behavior:

- Show a success confirmation.
- Navigate to `/registrations/{registration_id}` or provide a clear link.
- Keep the status visible, usually `SUBMITTED`.

Validation and error states:

- Empty `adapter_name`: show client-side required-field message.
- Empty `repository_location`: show client-side required-field message.
- Invalid `contact_email`: show client-side email message and still rely on
  backend `422` as source of truth.
- Backend `400`: show operation-level error, such as unsupported repository URL
  or missing local path.
- Backend `422`: show request validation errors near fields when possible.

Manual verification reference:

```bash
http POST :8000/api/v1/registrations \
  adapter_name="Manual Example Adapter" \
  repository_location=/tmp/biocypher-api-manual-adapter \
  contact_email=maintainer@example.org
```

## Registration Detail

Primary route suggestion:

```text
/registrations/:registrationId
```

Endpoints:

```text
GET /api/v1/registrations/{registration_id}
GET /api/v1/registrations/{registration_id}/events
POST /api/v1/registrations/{registration_id}/process
POST /api/v1/registrations/{registration_id}/revalidate
```

Detail response fields used by UI:

```text
registration_id
adapter_name
adapter_id
repository_location
repository_kind
status
created_at
contact_email
metadata_path
metadata
profile_version
updated_at
uniqueness_key
validation_errors
```

Event response fields used by UI:

```text
event_id
event_type
message
profile_version
error_details
observed_checksum
mlcroissant_valid
schema_valid
started_at
finished_at
registry_entry_id
```

Primary UI regions:

- registration summary
- status badge
- repository information
- validation result/errors
- current metadata section, if present
- event timeline
- action area

Action rules:

```text
SUBMITTED
  Show "Process registration".

INVALID
  Show "Revalidate".

FETCH_FAILED
  Show "Revalidate".

VALID
  Show read-only status and canonical information.
```

The backend remains the source of truth. If the frontend shows an action that
the backend rejects, display the backend error and refresh the detail view.

Refresh behavior after actions:

- `process` returns the updated registration detail shape.
- `revalidate` returns the updated registration detail shape.
- After either action, refresh the events endpoint or update the event list from
  a follow-up fetch.

Empty/loading/error states:

- Loading: show skeleton or progress area for summary and events.
- `404`: show registration not found.
- `400`: show action failed with backend detail.
- No events: show a neutral "No event history yet" message.
- No metadata: show "Metadata not discovered yet."

## Registry Operations

Primary route suggestion:

```text
/registry
```

Endpoints:

```text
GET /api/v1/registry/registrations
GET /api/v1/registry/registrations?status=INVALID&latest_event=FETCH_FAILED
POST /api/v1/registry/refreshes
GET /api/v1/registry/refreshes/latest
GET /api/v1/registry/entries
```

Registration table fields:

```text
registration_id
adapter_name
adapter_id
repository_kind
repository_location
status
latest_event_type
created_at
updated_at
contact_email
profile_version
uniqueness_key
```

Supported filters:

```text
status
latest_event
```

The backend uses strict query values. Unsupported values return `422`.

Batch refresh response fields:

```text
active_sources
processed
valid_created
unchanged
invalid
duplicate
rejected_same_version_changed
fetch_failed
```

Latest refresh response fields:

```text
refresh_id
started_at
finished_at
active_sources
processed
valid_created
unchanged
invalid
duplicate
rejected_same_version_changed
fetch_failed
```

Primary UI regions:

- status/event filters
- active registration table
- batch refresh action
- latest refresh summary
- optional canonical entries table

Action behavior:

- Disable "Run batch refresh" while request is in flight.
- On success, update the summary and reload the registration table.
- On failure, keep the previous table visible and show an operation-level error.

Empty states:

- No active registrations: show a clear empty state and link to registration form.
- No latest refresh: display "No batch refresh has been run yet." The endpoint
  returns `404` in this case.

## Adapter Catalog

Primary route suggestion:

```text
/adapters
```

Endpoint:

```text
GET /api/v1/adapters
```

Catalog item fields:

```text
adapter_id
adapter_name
latest_version
version_count
```

Important behavior:

- Only canonical valid registry entries appear in the adapter catalog.
- `SUBMITTED`, `INVALID`, and `FETCH_FAILED` registrations should not appear.
- This is a public read model, not a maintainer operations table.

Empty state:

- If `items` is empty, show "No valid adapters are registered yet."

## Adapter Detail

Primary route suggestion:

```text
/adapters/:adapterId
```

Endpoints:

```text
GET /api/v1/adapters/{adapter_id}
GET /api/v1/adapters/{adapter_id}/versions/{version}/metadata
```

Detail fields:

```text
adapter_id
adapter_name
latest_version
versions[]
```

Version fields:

```text
adapter_id
adapter_name
adapter_version
registry_entry_id
profile_version
metadata_checksum
created_at
updated_at
```

Metadata response fields:

```text
adapter_id
adapter_version
registry_entry_id
metadata
```

UI behavior:

- Show all registered versions.
- Make the latest version visually clear.
- Fetch full metadata only when the user opens a version detail or metadata
  panel. Do not fetch full metadata for the catalog list.
- Render metadata in a readable JSON viewer or structured summary.

Error states:

- `404` adapter not found.
- `404` version not found.

## Metadata Workspace

Primary route suggestion:

```text
/metadata
```

This area is more advanced because the current API works with server-side paths
visible to the backend process. The frontend must communicate that clearly.

### Validate Metadata

Endpoint:

```text
POST /api/v1/metadata/validate
```

Request fields:

```text
metadata
kind
```

Allowed `kind` values:

```text
auto
adapter
dataset
```

UI behavior:

- Provide a JSON editor or upload/paste flow.
- Default to `auto`.
- Show validation summary and per-check details.
- If auto-detection fails, ask the user to choose adapter or dataset.

### Generate Dataset Metadata

Endpoint:

```text
POST /api/v1/metadata/datasets/generate
```

Request fields:

```text
input_path
generator
validate
name
description
url
license
citation
dataset_version
date_published
creators
extra_args
```

Allowed `generator` values:

```text
auto
croissant-baker
native
```

Default UI behavior:

- `validate` should default to `true`.
- `generator` can default to `auto` or `native` depending on product choice.
- Make clear that `input_path` is a backend-visible path, not a browser file
  upload.

Response fields:

```text
metadata
generator
stdout
stderr
warnings
validation
```

### Generate Adapter Metadata

Endpoint:

```text
POST /api/v1/metadata/adapters/generate
```

Request fields:

```text
name
description
version
license
code_repository
dataset_paths
generated_datasets
validate
creators
keywords
adapter_id
programming_language
target_product
generator
dataset_generator
```

Generated dataset item fields:

```text
input
validate
name
description
url
license
citation
dataset_version
date_published
creators
extra_args
```

Allowed values:

```text
generator: native
dataset_generator: auto, croissant-baker, native
```

Default UI behavior:

- `validate` should default to `true`.
- `programming_language` should default to `Python`.
- `target_product` should default to `BioCypher`.
- Require at least one creator and one keyword.
- Require at least one existing dataset path or generated dataset.

Response fields:

```text
metadata
generator
dataset_generator
stdout
stderr
warnings
validation
```

## Shared UI State Rules

### Loading

Use loading indicators for:

- initial page data fetch
- process/revalidate actions
- batch refresh
- metadata generation
- metadata validation

Disable only the action that is currently running. Avoid freezing the whole
page unless necessary.

### Empty

Use explicit empty states for:

- no registrations
- no events
- no latest refresh
- no valid adapters
- no metadata discovered yet

Empty states should suggest the next useful action.

### Success

Success states should show:

- what changed
- current status
- link to detail view when available

### Errors

For backend errors, prefer this display order:

```text
field-level validation errors
operation-specific error detail
generic fallback message
```

Do not hide backend validation errors behind generic toast messages. They are
important in this project.

## Frontend Implementation Checklist

Before implementing a screen:

- Identify the endpoint(s) from this document.
- Confirm the endpoint works in `/docs` or with HTTPie.
- Define TypeScript types matching the response fields used by the UI.
- Implement one API-client function per backend operation.
- Design loading, empty, success, and error states before adding styling polish.
- Keep backend status values as data, not as frontend business logic.

Before considering a screen complete:

- It handles `400`, `404`, and `422` responses where applicable.
- It does not request full metadata for list/table pages.
- It can recover after process/revalidate/refresh actions.
- It renders unknown event types without crashing.
- It has a manual verification path.

## Deferred Decisions

- Authentication and authorization for maintainer-facing registry operations.
- Pagination for large registration and adapter lists.
- Server-side sorting and search.
- Browser file upload support for metadata validation/generation.
- Whether the metadata workspace should remain an expert tool or become a main
  user-facing workflow.
- Whether public adapter catalog query helpers should move from API-only logic
  into shared core queries when a second consumer appears.
