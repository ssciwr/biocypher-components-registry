# Persistence Design

## Purpose

This document defines the persistence boundary for the BioCypher Components
Registry backend.

Persistence means Python code that communicates with storage systems. It is
separate from the database runtime itself.

```text
src/persistence/
  Python database adapter code inside the backend application.

db container or SQLite file
  Runtime storage outside the Python package.
```

## Design Direction

The persistence subsystem uses a ports-and-adapters approach.

```text
src/core
  owns business logic and defines persistence ports.

src/persistence
  implements those ports using concrete database technologies.

database runtime
  stores data, for example SQLite locally or PostgreSQL in production.
```

The core rule is:

```text
src/core defines what persistence behavior it needs.
src/persistence implements how that behavior is fulfilled.
```

## Code Layout

```text
src/
├── api/
├── core/
│   └── registration/
│       ├── service.py
│       ├── store.py
│       ├── models.py
│       └── errors.py
└── persistence/
    ├── __init__.py
    ├── factory.py
    ├── schema.py
    ├── tables.py
    ├── registration_store_base.py
    ├── registration_sqlite_store.py
    └── registration_postgres_store.py
```

Current implementation status:

```text
src/persistence/__init__.py
src/persistence/factory.py
src/persistence/schema.py
src/persistence/tables.py
src/persistence/registration_store_base.py
src/persistence/registration_sqlite_store.py
src/persistence/registration_postgres_store.py
```

SQLite and PostgreSQL share the SQLAlchemy implementation. The factory
selects and reuses stores for the active process/configuration.

## Boundary Diagram

```mermaid
flowchart TB
    API["src/api\nFastAPI routes"]
    Core["src/core\nBusiness logic"]
    Port["src/core/registration/store.py\nRegistrationStore port"]
    Adapter["src/persistence/registration_sqlite_store.py\nSQLite/PostgreSQL adapters"]
    Tables["src/persistence/tables.py\nSQLAlchemy tables"]
    DB[("SQLite file or PostgreSQL")]

    API --> Core
    Core --> Port
    Port --> Adapter
    Adapter --> Tables
    Adapter --> DB
```

## Responsibilities

`src/core` owns:

- registration use cases
- validation and terminal attempt rules
- duplicate policy
- checksum and event classification rules
- persistence ports such as `RegistrationStore`
- core result and status models

`src/persistence` owns:

- SQLAlchemy table metadata
- SQLite and PostgreSQL store implementations
- database connection/session helpers
- database-specific query implementation details
- future migration integration

The database runtime owns:

- stored data
- database process, when using PostgreSQL
- volumes or persistent files

## Registration Source Fields

`registration_sources` stores an accepted repository/local source and ownership:

```text
submitted_adapter_name
description
repository_location (unique after normalization)
source_kind
license_value / doi / cff_url
submitted_by_github_user_id
is_active
created_at / updated_at / last_checked_at / last_seen_at
current_registry_entry_id
```

Identity and name come from validated metadata; the owner comes from verified
authentication. New source, canonical entry and `VALID_CREATED` event are created
in one transaction only after acceptance. Failed first registrations create none
of them. Failed updates append events while preserving the accepted entry.

Canonical identity/version uniqueness and identity ownership are enforced during
acceptance, including concurrent submissions. Repository aliases normalize to
the same source. UI-only confirmation checkboxes and lifecycle `status` values
are not source columns.

## Registry Refresh Fields

`registry_refreshes` stores one row per batch refresh run:

```text
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
internal_failed
```

This table supports the API endpoint
`GET /api/v1/registry/refreshes/latest`, registration read clients, and
the CLI `show-latest-refresh` command. It stores summary counts only, not full
metadata payloads.

## Dependency Rules

Allowed:

```text
src/api -> src/core
src/api -> src/persistence for dependency wiring only
src/core -> src/core modules and ports
src/persistence -> registration store/query ports and models
src/persistence -> SQLAlchemy and database drivers
```

Disallowed:

```text
src/core business rules -> src/persistence concrete adapters
src/core business rules -> SQLAlchemy tables
src/persistence -> src/api
src/persistence -> frontend
frontend -> src/persistence
```

Delivery layers should use the shared persistence factory instead of directly
constructing concrete persistence adapters:

```text
src/persistence/factory.py
  build_registration_store(...)
```

Current callers:

```text
src/api/dependencies.py
cli.py
```

The factory uses `DATABASE_BACKEND` to select SQLite or PostgreSQL explicitly.
SQLite uses `SQLITE_DATABASE_PATH`; PostgreSQL uses the `POSTGRES_*` components. Stores and engines
are cached per process/configuration and disposed on shutdown. Core services
receive the store/query port. CLI publication checks database connectivity before
starting OAuth or metadata processing.

## Runtime Deployment

In Docker Compose, the backend image contains Python code:

```text
backend container
  src/api
  src/core
  src/persistence
```

The database is a separate runtime service only when using PostgreSQL:

```text
db container
  PostgreSQL server
  persistent volume
```

With SQLite, no separate database container is required. The SQLite file should
live in a stable local path or mounted Docker volume.

## Migration Notes

SQLite and PostgreSQL implement the same port and current table schema. Schema
initialization supports fresh databases; automatic upgrades of historical schemas
are not provided. Existing deployments need an explicit migration/export plan
before adopting the changed registration contract.

The migration path should preserve:

- the `RegistrationStore` core port
- registration event semantics
- canonical uniqueness on `adapter_id + "::" + version`
- checksum behavior
- non-blocking batch processing behavior
