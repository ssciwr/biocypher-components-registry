# Project Context

## 1. Project Overview

**Project Name:** BioCypher Components Registry (biocypher-components-registry)

**Purpose:**
Deliver a repository-based BioCypher adapter registry that replaces board-only tracking with validated, queryable, and reusable adapter metadata.

**Scope:**
The project covers adapter metadata registration and discovery through a repository workflow: adapter declaration, metadata ingestion from adapter repositories, schema validation, duplicate prevention, status tracking, run-level reporting, and programmatic metadata retrieval via an MCP-compatible interface.

**Note:** The project context is implementation-agnostic and excludes volatile details such as sprint plans, UI design choices, or specific storage technology decisions.

**Key Deliverables:**
- A GitHub repository that serves as the canonical BioCypher Components Registry.
- A standardized adapter registration input (`adapters.yaml` or equivalent).
- A metadata ingestion and validation workflow for `croissant.jsonld` files.
- Queryable canonical registry entries backed by the registration database.
- Validation outcomes per adapter (`VALID`/`INVALID`) with stored failure reasons for invalid entries.
- Run summary outputs with counts for processed, valid, invalid, duplicates, and revalidated adapters.
- An MCP-compatible metadata retrieval interface (or an MCP-ready contract/specification).
- SDLC documentation set including project context, raw ideas, derived user stories, and architecture documentation.


## 2. Rationale

The current community tracking approach (GitHub board) is useful for visibility but insufficient as a durable registry.

- Metadata quality is inconsistent over time (broken links, missing descriptions, stale records).
- Registration is not standardized end-to-end.
- There is no built-in quality/validation process to assess maturity.
- The current model is not agent-ready for programmatic discovery and retrieval.

The project exists to provide a reliable, scalable, and queryable registry foundation.


## 3. Stakeholders

- Adapter maintainers: produce and update adapter metadata in adapter repositories.
- Registry maintainers: define the validation schema and govern registry operations, including ingestion, validation, storage, and reporting workflows.
- Users (researchers/developers): discover adapters and evaluate reuse suitability.
- Agent/MCP clients: programmatically search and retrieve adapter metadata for downstream automation.


## 4. Constraints

- Adapter metadata contract is centered on a single `croissant.jsonld` file per adapter repository.
- Metadata validation must follow one shared validation schema at runtime.
- Processing must be resilient: invalid adapters cannot block analysis of others.
- Duplicate adapter entries must be prevented by an agreed uniqueness policy.
- Validation outcomes must be auditable (`VALID`/`INVALID` plus error details and run summary).

**Note:** Solution implementation details (storage engine, interface details) may evolve, but these constraints represent stable project direction.


## 5. Key Concepts / Terminology

- Adapter: A reusable BioCypher component/integration.
- Registry: Canonical catalog of adapters and associated metadata.
- `croissant.jsonld`: Metadata artifact used as adapter registration contract.
- Validation schema: Shared rule set used to evaluate metadata compliance.
- `VALID` / `INVALID`: Canonical status values for adapter metadata validation outcomes.
- Revalidation: On-demand re-execution of validation for previously failed adapters.
- Run summary: Per-execution report with timestamped run ID and aggregate counters.
- MCP interface: Programmatic interface used by agent clients to discover/retrieve adapter metadata.


## 6. Assumptions

- Adapter repositories are the source of truth for adapter metadata files.
- Metadata evolves over time and requires periodic or on-demand re-checking.
- Users need low-friction discovery and retrieval rather than manual board inspection.
- Programmatic consumption (for example via MCP) is a first-class project goal.
- Governance expects traceable outcomes for each registration/validation run.


## 7. Reference Links

- BioCypher project: https://github.com/biocypher/biocypher
- Raw ideas and workflow baseline: `sdlc_docs/a_requirements/a-1_raw_ideas.md`
- Derived user stories: `sdlc_docs/a_requirements/a-2_user_stories.md`


## 8. Revision History

| Date       | Change                                                                         |
| ---------- | ------------------------------------------------------------------------------ |
| 2026-03-16 | Initial project context created from approved raw ideas and workflow baseline. |


## Next:
- Go to the folder `a_requirements`.
