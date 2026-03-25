# ADR-0001: Repository Layout

## Status

Accepted

## Context

The project currently mixes several responsibilities in one repository:

- existing Python backend logic
- a temporary server-rendered web layer
- future API concerns
- future React frontend work
- persistence and registry processing behavior

The architecture must support incremental implementation now and a future
frontend repository split later. The frontend is the component expected to move
out of this repository in the future. The Python backend and Python API should
remain together.

## Decision

Use this repository layout:

```text
biocypher-components-registry/
├── frontend/
├── src/
│   ├── api/
│   ├── core/
│   └── persistence/
├── tests/
├── sdlc_docs/
├── pyproject.toml
└── README.md
```

The folder responsibilities are:

- `frontend/`: React frontend workspace and future repository split candidate.
- `src/api/`: thin Python HTTP API delivery layer.
- `src/core/`: existing reusable Python backend logic and future backend
  application/domain code, including application-facing ports.
- `src/persistence/`: database adapters, SQLAlchemy table definitions,
  connection helpers, and SQLite/PostgreSQL persistence implementations.
- `tests/`: Python unit, integration, and BDD tests.
- `sdlc_docs/`: requirements, architecture, design notes, and ADRs.

Do not introduce an `apps/` or `packages/` layout at this stage.

## Consequences

Positive:

- The layout stays understandable and close to the current repository shape.
- The frontend can be moved later without untangling Python packaging.
- Backend and API code stay together under one Python project.
- Existing `src/core` code can remain in place during the migration.
- Database-specific code has an explicit home without putting business logic in
  database adapters.

Tradeoffs:

- The repository will temporarily contain both frontend and backend tooling.
- The top-level `frontend/` and Python `src/` both contain source code, so
  documentation must clearly distinguish frontend source from Python source.
- The Python backend now has one more top-level package under `src`, so
  dependency rules must prevent `src/core` from depending on concrete
  persistence adapters.
- The final frontend repository layout should be documented separately when the
  split is planned.

## Follow-Up

- Keep `sdlc_docs/b_design/architecture.md` as the main architecture guide.
- Update README setup instructions after `src/api/` and `frontend/` exist.
