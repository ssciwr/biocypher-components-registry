# Frontend Penpot Design Tracking

## Purpose

This document is a working design-tracking note for the future React frontend.

It is intended to help shape the look and feel of the application before implementation begins in React. The current visual inspiration is the Apache Airflow Registry, especially its clean landing page, card-based browsing, strong search focus, and professional registry-style presentation.

This note is not a final specification yet. It is a place to track:

- design goals
- visual references
- target pages
- user flows
- Penpot planning progress
- decisions that should later inform React implementation

## Design Intent

The frontend should:

- feel professional, modern, and trustworthy
- support both metadata creation and registry operations
- eventually replace the current server-rendered frontend responsibilities
- reuse the current backend business logic instead of duplicating it in the UI
- remain compatible with a future backend move to FastAPI or Flask

## User Roles

The frontend should distinguish between normal user workflows and maintainer workflows.

### Users

Users can:

- explore adapters
- create Croissant metadata for adapters
- register adapters
- read documentation or guidance

Suggested normal-user navigation:

- `Create`
- `Register`
- `Explore`
- `Docs`

### Maintainers

Maintainers can:

- inspect registry internals
- monitor active registration sources
- review validation and processing outcomes
- trigger registry operations such as refresh or revalidation
- apply online changes where supported by the backend

Suggested maintainer navigation can include normal-user navigation plus maintainer-only areas:

- `Create`
- `Register`
- `Explore`
- `Docs`
- `Registry`
- `Monitoring`

## Primary Visual Reference

Reference inspiration:

- Apache Airflow Registry

Qualities to borrow:

- clear navigation
- spacious layout
- strong search-first discovery
- clean cards for browseable items
- lightweight but polished visual language
- modern hero section with soft gradients and concise messaging

## Current Web UI Scope Found In `src`

The current web UI already covers more than registry administration. It includes:

- landing/start page
- resume previous session
- preload metadata from YAML
- start metadata creation from scratch
- multi-step adapter metadata generation form
- dataset management inside the generation flow
- field preview / field editing behavior for datasets
- generated result page with preview and download
- adapter registration form
- registration detail and event history
- registry operations overview
- batch refresh action/result state
- revalidation action/result state

## Candidate Page Inventory

### A. Metadata Creation

1. Landing / start page
2. Resume session state
3. YAML preload / import state
4. Metadata generation workspace
5. Adapter details section
6. Dataset list / dataset manager
7. Dataset editor
8. Field mapping / field preview editor
9. Review summary
10. Generated result page
11. Download state

### B. Registry Operations

12. Registration form page
13. Registration detail / status page
14. Revalidation state
15. Registry operations page
16. Batch refresh summary state

### C. Discovery / Public Catalog

17. Discovery landing page
18. Adapter browse page
19. Adapter search results state
20. Adapter detail page

### D. Support States

21. Empty state: no saved session
22. Empty state: no registered sources
23. Empty state: no generated file
24. Error state: invalid submission
25. Error state: validation failed
26. Error state: fetch failed

## Candidate User Flows

- Start from the landing page and choose how to begin metadata creation
- Resume a previously saved metadata authoring session
- Preload a YAML file and continue editing
- Create adapter metadata from scratch
- Add datasets and refine field definitions
- Review and generate a Croissant JSON-LD file
- Inspect the generated result and download the file
- Submit a new adapter registration
- Process a registration and inspect status/history
- Revalidate a failed registration
- Run a batch refresh and inspect the latest source outcomes
- Browse adapters from a discovery-oriented homepage
- Search for adapters and open adapter details

## Registration Form Fields

The registration form should collect:

- adapter name
- repository location
- contact email for status notifications
- confirmation that a `croissant.jsonld` file exists at the repository root

The contact email is used to notify the submitter about registration processing status, validation outcomes, and follow-up actions when supported by the backend.

Suggested confirmation text:

- `I confirm that a croissant.jsonld file exists at the root of this repository.`

## Recommended First Penpot Scope

For the first Penpot iteration, focus only on the highest-value screens:

- Landing / start page
- Metadata generation workspace
- Generated result page
- Registration form page
- Registration detail page
- Registry operations page

Second iteration:

- Dataset editor
- Field mapping editor
- Discovery landing page
- Adapter browse page
- Adapter detail page

## Penpot Workflow Plan

### Stage 1: Define pages and flows

- list the target pages
- list the main user flows
- decide which screens belong to the first design pass

### Stage 2: Set up Penpot project structure

- create one project for the frontend
- create one file for exploration or wireframes
- create one page for references
- create one page for low-fidelity wireframes
- create one page for polished mockups
- create one page for reusable components

### Stage 3: Build a reference board

- capture screenshots and notes from Airflow Registry
- identify layout patterns to reuse
- identify patterns that do not fit this project

### Stage 4: Define look and feel

- color direction
- typography direction
- spacing scale
- card style
- form style
- table style
- status indicators

### Stage 5: Design the first wireframes

- landing page
- generator workspace
- result page
- registration form
- registration detail
- registry operations page

### Stage 6: Create polished UI mockups

- apply colors, type, spacing, and component consistency
- refine hierarchy and readability
- improve desktop and mobile behavior

### Stage 7: Create reusable UI components

- top navigation
- hero block
- buttons
- form fields
- cards
- tables
- status badges
- summary metrics

### Stage 8: Prepare handoff for implementation

- map screens to frontend routes
- map interactions to backend endpoints
- identify reusable React components

## Design Principles For This Project

- backend business logic stays in the backend
- the frontend should be API-driven
- the UI should support both technical and non-technical users
- forms should reduce confusion and guide completion
- registry workflows should feel transparent and auditable
- discovery pages should feel inviting, simple, and easy to scan
- maintainer registry tables should follow familiar dashboard/data-grid patterns, similar to Material UI tables, with visible filters, column-oriented filtering, clear status chips, and row-specific CTA actions

## Open Questions

- Should the final product emphasize metadata authoring first, or discovery first?
- Should the homepage be a workflow hub, a public discovery landing page, or both?
- Should metadata creation feel like a long guided wizard or a dashboard-style workspace?
- How much of the Airflow Registry style should be borrowed directly versus adapted?

## Progress Log

- [x] Added `US-12 React front-end migration`
- [x] Added frontend architecture design note
- [x] Identified current web UI scope from `src/core/web`
- [x] Drafted expanded page inventory for Penpot planning
- [ ] Finalize page list for first Penpot pass
- [ ] Finalize user flows for first Penpot pass
- [ ] Set up Penpot project structure
- [ ] Create first wireframes
