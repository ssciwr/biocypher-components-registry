# Project Context

## 1. Project Overview

**Project:** BioCypher Components Registry (`biocypher-components-registry`)

**Purpose:** Replace board-only adapter tracking with a validated, queryable,
and reusable registry of BioCypher adapter metadata.

The project provides a common publication and discovery workflow through:

- a React application for users and adapter maintainers;
- a FastAPI REST API for browser and programmatic clients;
- a CLI for generation, validation, publication, and trusted maintenance; and
- shared Python services for validation, registration, generation, and storage.

### Current Product Scope

The implemented product includes:

- GitHub-authenticated registration of public HTTPS repositories;
- server-local source support for development and integration workflows;
- retrieval and validation of root-level `croissant.jsonld` metadata;
- metadata-derived adapter identity and ownership;
- duplicate prevention and atomic first acceptance;
- owner-authorized updates that preserve accepted metadata on failure;
- canonical registry entries and terminal update history;
- public adapter discovery and metadata reads;
- adapter and dataset Croissant metadata generation;
- ephemeral browser file/folder uploads for dataset generation;
- SQLite and PostgreSQL persistence; and
- manual CLI batch refresh with persisted summaries.

### Near-Term Nice to Have

- **Versioned database schema migrations:** introduce revision tracking and
  tested upgrade procedures for existing SQLite and PostgreSQL databases. This
  is outside the current MVP and should be prioritized before persistent
  deployments need to retain data across schema-changing releases. Alembic is a
  likely implementation option, not an accepted technology decision.

### Longer-Term Future Scope

The following remain product goals rather than current capabilities:

- scheduled registry refresh;
- automatic retry and notification delivery;
- an MCP delivery adapter for registry discovery and retrieval;
- horizontally coordinated dataset-upload sessions.

The optional agentic workspace is a separate adapter-creation capability. It is
not the future MCP registry retrieval interface and has its own API and security
boundary.

## 2. Rationale

The community GitHub board is useful for visibility but is not a durable
registry:

- metadata quality can drift through missing fields, stale records, or broken
  links;
- publication and updates lack one consistent validation workflow;
- accepted metadata and failed attempts are difficult to distinguish;
- duplicate identities and versions are difficult to prevent manually; and
- applications and agents need structured discovery instead of board inspection.

The registry creates a reliable foundation for publication, discovery,
traceability, and future programmatic integrations.

## 3. Stakeholders

| Stakeholder | Need |
| --- | --- |
| Adapter maintainers | Generate metadata, register public repositories, inspect diagnostics, and update owned adapters. |
| Registry users | Discover accepted adapters and evaluate their metadata and versions. |
| Registry operators | Configure deployment, run trusted batch maintenance, and inspect summaries. |
| API consumers | Read stable registry data through a documented HTTP contract. |
| Frontend contributors | Build workflows without depending on Python internals or database tables. |
| Backend contributors | Reuse the same rules across API and CLI interfaces. |
| Future MCP consumers | Discover and retrieve registry metadata through a future shared read boundary. |

## 4. Stable Product Constraints

- A publishable remote source is a public HTTPS Git repository with
  `croissant.jsonld` at its root on the default branch.
- Server-local paths are supported for development and integration, not as
  browser-local repository paths.
- One shared validation contract governs API, CLI, registration, and metadata
  utilities.
- Only accepted metadata becomes a canonical registry entry.
- Rejected first registrations create no source, entry, or event record.
- Failed updates preserve the last accepted metadata and append terminal history.
- Canonical adapter identity and version combinations must be unique.
- The verified GitHub account owns accepted registration sources.
- One source failure must not stop a manual batch refresh.
- Browser dataset bytes must remain transient and outside durable storage.
- Current upload sessions are process-local and therefore constrain backend
  scaling until coordination is redesigned.

Implementation details may evolve, but changes must preserve these product
rules or record an explicit architectural decision.

## 5. Key Concepts

| Term | Meaning |
| --- | --- |
| Adapter | Reusable BioCypher integration described by Croissant metadata. |
| Registry | Canonical catalog of accepted adapters and their metadata. |
| Remote repository | External Git source accessed over HTTPS from an allowed host. |
| Local source | Repository directory visible to the backend filesystem for development or integration. |
| Registration source | Accepted remote repository or local source owned by a verified identity. |
| `croissant.jsonld` | Root metadata document used as the adapter publication contract. |
| Registry entry | Canonical accepted metadata for one adapter identity and version. |
| Published version | Version of the currently accepted entry. |
| Attempt | One terminal registration or update operation. |
| Attempt status | `SUCCEEDED` or `FAILED`, independent of publication state. |
| Update applied | Whether an operation changed the accepted entry. |
| Validation profile | Versioned schema and validation rules applied to metadata. |
| Batch refresh | Trusted CLI operation that checks active sources independently. |
| Upload artifact | Complete or sampled transient bytes prepared from a dataset file. |
| MCP registry adapter | Future delivery interface over shared registry read services. |

## 6. Assumptions

- Remote adapter repositories remain the source of truth for published metadata.
- Metadata changes over time and needs explicit update or maintenance workflows.
- Users need actionable validation diagnostics, not only valid/invalid labels.
- Public discovery must expose accepted metadata even when the latest update
  attempt failed.
- SQLite is suitable for local development; PostgreSQL is the production-oriented
  persistence option.
- Manual batch maintenance is sufficient for the current MVP.
- Distributed coordination should be introduced only when actual availability or
  throughput needs justify its cost.

## 7. Success Criteria

The project succeeds when:

- valid metadata can be published and discovered consistently;
- invalid first candidates leave no partial registry state;
- failed updates cannot replace accepted metadata;
- duplicate identities, versions, and normalized sources are rejected;
- API and CLI workflows preserve the same core behavior;
- validation errors identify actionable checks and positions when available;
- dataset uploads are bounded, ephemeral, and cleaned up; and
- operators can inspect isolated batch outcomes and aggregate summaries.

## 8. Authoritative Documentation

| Topic | Source |
| --- | --- |
| System architecture and boundaries | [Architecture](b_design/architecture.md) |
| Requirements and user stories | [User stories](a_requirements/a-2_user_stories.md) |
| Original problem statements | [Raw ideas](a_requirements/a-1_raw_ideas.md) |
| Exact REST operations and schemas | Runtime Swagger at `/docs` and OpenAPI at `/openapi.json` |
| Dataset generator behavior | [Dataset generation backends](../docs/dataset_backends.md) |
| Registration persistence | [Registration database design](b_design/database/registration_database_design.md) |
| Deployment and upload security | [Deployment and security architecture](../docs/deployment.md) |

## 9. Revision History

| Date | Change |
| --- | --- |
| 2026-03-16 | Initial context derived from the approved ideas and workflow baseline. |
| 2026-11-13 | Aligned scope, terminology, constraints, and future work with the implemented registry architecture. |
