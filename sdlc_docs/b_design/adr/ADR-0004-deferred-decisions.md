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

Decision: do not generate frontend API types from OpenAPI yet.

Generate or document frontend API types when the React frontend starts calling
real API endpoints.

Reason:

- OpenAPI should exist early.
- Type generation is valuable only once the React app consumes the API.
- Deferring avoids adding frontend tooling before it is needed.

### Registry Run Summary Persistence

Decision: decide after the initial API skeleton.

Start by returning the current counter-based summary through the API. Add a
persisted run table, such as `registration_runs` or `processing_runs`, when
batch refresh becomes a first-class API workflow.

Reason:

- current behavior can be wrapped incrementally
- project requirements call for timestamped run identifiers and aggregate run
  reporting
- the persistence shape should be designed with API response and reporting
  needs visible

### Maintainer Authentication

Decision: defer the mechanism, but preserve the boundary.

Treat `Registry`, refresh, and revalidation operations as maintainer-facing. Do
not hardcode an auth approach until deployment assumptions are clearer.

Potential future options:

- local-only access
- reverse-proxy authentication
- GitHub OAuth
- institutional SSO
- API tokens

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

- Revisit run summary persistence after the initial API routes exist.
- Revisit authentication before exposing maintainer workflows beyond local
  development.
- Revisit MCP after registry read/query services are stable.
- Keep any future automation on top of the shared registration and registry
  services rather than reintroducing a separate scripts pipeline.
