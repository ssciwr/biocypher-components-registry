# ADR-0004: Deferred Decisions

## Status

Accepted

## Context

Several architecture questions are important but do not need to block the next
implementation step. Deciding them too early would risk designing around unknown
deployment, API, or frontend constraints.

## Decision

Defer the following decisions while preserving their architecture boundaries.

### Frontend API Type Generation

Implemented. The React application consumes generated TypeScript types and
clients under `frontend/src/api/client/`. Run `pnpm run openapi-ts` from
`frontend/` after changing the FastAPI contract; the command exports the
OpenAPI document before regenerating the client.

The original boundary remains: FastAPI's OpenAPI schema is the source for
frontend transport types, so API models are not maintained independently in
React.

### Registry Run Summary Persistence

Implemented for CLI batch refreshes in `registry_refreshes`. Each completed run
records its identifier, timestamps and outcome counters, including separate
fetch and internal failures. Read the latest summary through
`GET /api/v1/registry/refreshes/latest` or `show-latest-refresh`.

The original reporting boundary remains: summaries are produced by shared core
services and persisted through the store port. There is no public HTTP batch
mutation endpoint or scheduled worker in this implementation.

### Maintainer Authentication

Registration now requires a verified GitHub account. Browser requests use the
existing OAuth cookie session; CLI `register` and `update` use device
authorization and call shared services directly after verification and temporary
token revocation. Owner checks protect published adapter updates.

Batch refresh remains a trusted CLI maintenance operation. A broader
administrator role, institutional SSO, API tokens and authorization for future
operator workflows remain deployment decisions. This change does not redefine
the agentic workspace's authentication boundary.

### MCP Retrieval

Decision: defer until registry read/query services stabilize.

MCP should reuse backend read services, not define a separate registry query
model prematurely.

Reason:

- MCP is a documented project goal
- HTTP API and MCP should use the same backend read behavior
- implementing MCP too early could couple it to unstable database or API
  details

### Legacy Registry Scripts

Decision: retire the legacy scripts and keep registry automation on shared
core services.

The old `scripts/fetch_adapters.py` and `scripts/generate_registry.py`
pipeline has been removed. Future automation should use the maintained CLI/API
workflow or a new adapter that calls the same backend services.

Reason:

- the long-term goal should be one registry workflow built on shared backend
  services
- keeping documentation for deleted scripts creates project drift
- the CLI and API now provide the maintained paths for refresh and registry
  inspection

## Consequences

Positive:

- The next implementation step stays focused on the API skeleton.
- The architecture preserves room for admin, MCP, reporting, and script
  migration without over-designing them now.

Tradeoffs:

- These questions must be revisited later.
- Future work should not use the deferral as a reason to ignore boundaries.

## Follow-Up

- Keep persisted batch summaries aligned with processing outcome counters.
- Revisit administrator authorization before exposing global maintenance actions.
- Revisit MCP after registry read/query services are stable.
- Keep any future automation on top of the shared registration and registry
  services rather than reintroducing a separate scripts pipeline.
