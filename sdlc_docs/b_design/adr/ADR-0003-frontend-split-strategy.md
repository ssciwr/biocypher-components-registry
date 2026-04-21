# ADR-0003: Frontend Split Strategy

## Status

Accepted

## Context

The project needs a React frontend, but the API contract and workflows are
still evolving. The frontend should start inside the current repository for
development speed and later move to a separate repository when the boundary is
stable.

## Decision

Start the React frontend in top-level `frontend/`.

Treat `frontend/` as the future repository split candidate.

Keep Python backend, API, and persistence adapter code together under `src/`.

After the future split, this repository should keep only backend/API concerns:

```text
biocypher-components-registry/
├── src/
│   ├── api/
│   ├── core/
│   └── persistence/
├── tests/
├── sdlc_docs/
├── pyproject.toml
└── README.md
```

The future frontend repository layout should be documented in the frontend
repository or in a frontend-specific design document when the split is planned.
This backend/API architecture should only define the boundary.

## Consequences

Positive:

- Development can begin without coordinating multiple repositories.
- The API contract can mature before the split.
- The frontend is physically easy to move later.
- Backend/API documentation remains focused on backend/API responsibilities.

Tradeoffs:

- The current repository will temporarily include Node/frontend tooling once
  the frontend is scaffolded.
- CI will eventually need to distinguish Python checks from frontend checks.
- The split should not happen until the API contract is stable enough for
  independent frontend development.

## Split Criteria

Move `frontend/` to a separate repository only after:

- the first real workflows run end to end through the API
- the API contract is stable enough for independent frontend development
- local development setup is documented
- deployment assumptions are known
- frontend tests cover critical workflows
- the frontend has no Python or backend-filesystem coupling

## Follow-Up

- Keep React dependent on HTTP API contracts only.
- Use `VITE_API_BASE_URL` or equivalent frontend configuration when API
  integration begins.
- Document frontend repository structure separately before the actual split.
