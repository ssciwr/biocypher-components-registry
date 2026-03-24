# User Stories

- ## [10.03.2026]
  
#### US-01 Adapter metadata file exists

**As an** adapter maintainer
**I need** to include exactly one `croissant.jsonld` file in my adapter repository
**So that** the registry can find and process my adapter metadata automatically

##### Details and Assumptions
- The file name is fixed: `croissant.jsonld`.
- Repositories with no file, or with multiple matching files, are rejected.
- The metadata file must follow the schema used by the registry.

##### Acceptance Criteria

```gherkin
Given an adapter repository submission
When the repository has exactly one file named croissant.jsonld
Then the registration flow proceeds to validation

Given an adapter repository submission
When croissant.jsonld is missing or ambiguous
Then the system returns a clear discovery error
```

---

#### US-02 Guided metadata generation

**As an** adapter maintainer
**I need** a guided flow to generate `croissant.jsonld`
**So that** I can produce valid metadata with low effort

##### Details and Assumptions
- The guided flow collects mandatory fields first.
- The output must be directly usable by the validator.
- Two interfaces are planned: a CLI and a web UI.

##### Acceptance Criteria

```gherkin
Given a maintainer providing mandatory metadata inputs
When the guided flow completes
Then a croissant.jsonld file is generated

Given a generated croissant.jsonld file
When it is validated
Then it passes schema checks for mandatory fields
```

---

#### US-03 Versioned validation profile

**As a** registry maintainer
**I need** one active, versioned validation profile
**So that** all adapter metadata is checked consistently

##### Details and Assumptions
- Only one active profile version is used per run.
- Profile changes are versioned.

##### Acceptance Criteria

```gherkin
Given a registration run
When validation starts
Then the system uses exactly one active validation profile version

Given a completed run
When run details are inspected
Then the profile version used is recorded
```

---

#### US-04 Repository submission

**As an** adapter maintainer
**I need** to submit my adapter name and repository location to the registry
**So that** the system can register my adapter for discovery and validation

##### Details and Assumptions
- Submission includes at least an adapter identifier/name and a repository location.
- Repository location can be a local path or a repository URL.
- A successful submission creates a registration request that can be processed by the registry workflow.

##### Acceptance Criteria

```gherkin
Given a maintainer provides a valid adapter name and repository location
When the submission is accepted
Then the system creates a registration request for that adapter
```

---

#### US-04a Registration UI and submission persistence

**As an** adapter maintainer
**I need** a user interface to submit adapter registration details
**So that** I can register my adapter without editing registry internals

##### Details and Assumptions
- The registration interface can be a web UI, CLI, or both.
- Submission details are stored in a live database.
- The stored record includes enough information to trigger discovery and validation later.

##### Acceptance Criteria

```gherkin
Given a maintainer opens the registration interface
When the maintainer submits a valid adapter name and repository location
Then the system stores the submission in the database
And the submission receives a tracked registration status
```

---

#### US-05 Persist valid adapter records

**As a** registry system maintainer
**I need** valid adapters to be stored with status `VALID`
**So that** downstream consumers can reliably query approved metadata

##### Details and Assumptions
- Metadata persistence and status assignment happen in the same flow.
- The registry should use a database system such as PostgreSQL or SQLite.
- The selected storage should be lightweight at first and support future growth.

##### Acceptance Criteria

```gherkin
Given a metadata file that passes validation
When registration finishes
Then the adapter record is persisted
And the adapter status is VALID
```

---

#### US-06 Prevent duplicates

**As a** registry system maintainer
**I need** duplicate adapter submissions to be blocked
**So that** the registry remains canonical and consistent

##### Details and Assumptions
- The uniqueness key policy is configurable and should use `adapter_id+version`.
- `adapter_id` is the normalized slug form of the adapter identity and is preferred over the display name.
- This avoids duplicate misses caused by case, spacing, or punctuation differences in adapter names.
- A database is used to enforce this rule.

##### Acceptance Criteria

```gherkin
Given an adapter already stored with a uniqueness key
When another submission uses the same uniqueness key
Then the system rejects the new submission as duplicate
```

---

#### US-06a Registration database architecture and event history

**As a** registry system maintainer
**I need** the registration persistence layer to separate submitted sources, canonical valid entries, and processing history
**So that** the registry can support auditable processing, duplicate-safe canonical storage, checksum-based change detection, and future revalidation/reporting workflows

##### Details and Assumptions
- The database design uses three core tables: `registration_sources`, `registry_entries`, and `registration_events`.
- `registration_sources` stores submitted repositories or local sources that the system tracks.
- `registry_entries` stores only canonical valid adapter entries that downstream consumers can query.
- `registration_events` stores the append-only processing history for every attempt and outcome.
- The canonical uniqueness key for valid entries is `adapter_id+version`.
- Processing history must include successful, invalid, duplicate, and unchanged outcomes.
- Checksum-based unchanged detection is part of the architecture so the system can avoid unnecessary reprocessing.
- The design should support a future migration from SQLite to PostgreSQL without changing the high-level service behavior.

##### Acceptance Criteria

```gherkin
Given a maintainer submits a repository source
When the submission is stored
Then a source record exists in registration_sources
And a SUBMITTED event exists in registration_events

Given a source is processed and the metadata is valid
When registration finishes
Then a canonical valid record exists in registry_entries
And a VALID_CREATED event exists in registration_events

Given a source is processed and the metadata is invalid, duplicate, or unchanged
When registration finishes
Then the canonical registry state remains correct
And the outcome is recorded in registration_events with the appropriate event type
```

---

#### US-07 Persist invalid status and errors

**As an** adapter maintainer
**I need** failed validations to return persisted error details
**So that** I can correct metadata and resubmit quickly

##### Details and Assumptions
- Error details are stored per adapter and run.
- Failed validation jobs are stored in a dedicated table.

##### Acceptance Criteria

```gherkin
Given a metadata file that fails validation
When registration finishes
Then the adapter status is INVALID
And detailed validation errors are persisted and retrievable
```

---

#### US-08 Non-blocking batch registration

**As a** registry system maintainer
**I need** the registry to poll all active sources and process them in non-blocking batch runs
**So that** one bad adapter does not block all others and the registry stays up to date with the latest valid `croissant.jsonld`

##### Details and Assumptions
- The registry owns the update workflow by polling active rows in `registration_sources`.
- Batch runs process sources independently, so failures are isolated at source level.
- The default automated cadence is once per day.
- A manual or on-demand batch trigger is also available for urgent refreshes and testing.
- A thin web UI may expose the manual batch trigger and a summary of latest per-source outcomes.
- Successful processing updates the canonical registry only according to the existing versioning and duplicate rules.
- Failed fetches should be retried sooner than the normal polling cadence using a backoff strategy.
- Invalid metadata outcomes are stored in `registration_events` and retried in later polling rounds unless deactivated.
- Failed jobs and their causes are stored.

##### Acceptance Criteria

```gherkin
Given a batch with valid and invalid adapters
When one adapter fails validation
Then remaining adapters are still processed
And the run completes with mixed outcomes

Given active sources are scheduled for polling
When the automated batch workflow runs
Then the registry checks each active source for the latest croissant.jsonld
And valid updates are applied according to the canonical registration rules

Given a source fails to fetch during a polling run
When the batch workflow completes
Then the failure is recorded
And the source is eligible for an earlier retry than the normal polling cadence

Given a maintainer fixes metadata before the next scheduled run
When an on-demand batch or manual refresh is triggered
Then the source can be reprocessed immediately

Given a maintainer opens the registry operations view
When a manual batch refresh is triggered from the web UI
Then the UI shows the batch summary
And the latest per-source outcomes are visible
```

---

#### US-09 On-demand revalidation

**As an** adapter maintainer
**I need** to revalidate previously invalid adapters on demand
**So that** I do not have to wait for the next scheduled run

##### Details and Assumptions
- Revalidation targets adapters currently marked `INVALID`.
- The system uses stored run and status data to identify which adapters failed registration.

##### Acceptance Criteria

```gherkin
Given an adapter currently marked INVALID
When on-demand revalidation is triggered after metadata correction
Then the system reprocesses the adapter immediately
And updates its status accordingly
```

---

#### US-10 MCP metadata discovery and retrieval

**As a** user or agent client
**I need** an MCP interface to discover and retrieve adapter metadata
**So that** I can integrate adapter selection into automated workflows

##### Details and Assumptions
- MCP returns metadata.
- Adapter execution is handled by client applications unless explicitly supported in the future.

##### Acceptance Criteria

```gherkin
Given an MCP client request to list or fetch adapters
When the request is valid
Then the system returns machine-consumable adapter metadata
```

---

#### US-11 Run summary reporting

**As a** registry system maintainer
**I need** a summary for each registration/validation run
**So that** I can monitor quality, throughput, and failures

##### Details and Assumptions
- Each run has one run identifier and timestamp.
- Summary includes processed, VALID, INVALID, duplicates, and revalidated counts.

##### Acceptance Criteria

```gherkin
Given a completed registration/validation run
When run reporting is generated
Then a summary record exists with run ID and timestamp
And it includes counts for processed, VALID, INVALID, duplicates, and revalidated adapters
```

---

#### US-12 React front-end migration

**As a** registry system maintainer
**I need** a professional front-end built with React to replace the existing front-end responsibilities
**So that** the project has a maintainable user experience layer that reuses current backend logic and remains adaptable to a future FastAPI or Flask backend

##### Details and Assumptions
- The React application replaces the current server-rendered front-end responsibilities incrementally or fully.
- Existing backend business logic should remain reusable and should not be reimplemented in the front-end.
- Front-end to backend communication should use clear API boundaries so the UI can work with the current backend and support a future migration to FastAPI or Flask.
- The UI should cover the current major user flows, including metadata generation, registration submission, registration status review, revalidation, and registry operations.
- The front-end should be professional, responsive, and suitable for maintainers and contributors.

##### Acceptance Criteria

```gherkin
Given a user opens the registry application
When the React front-end is available
Then the user can access the main workflows through the new interface

Given the React front-end performs metadata generation or registration actions
When the user submits a request
Then the front-end uses existing backend logic through stable backend interfaces
And no core business rules are duplicated only in the front-end

Given the project migrates later to FastAPI or Flask
When the backend delivery mechanism changes
Then the React front-end can continue to operate with minimal workflow changes
Because integration is based on explicit API contracts rather than server-rendered page coupling
```

### Check gate
- [x] Create GitHub issue cards for these user stories.

---
