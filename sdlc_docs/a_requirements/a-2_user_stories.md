# User Stories

- ## [10.03.2026]

#### US-01 Adapter metadata file exists

**As an** adapter maintainer
**I need** to include exactly one `croissant.jsonld` file in my adapter repository
**So that** the registry can find and process my adapter metadata automatically

##### Details and Assumptions
- The file name is fixed: `croissant.jsonld`.
- Remote registration resolves root-level metadata on the default branch; local discovery rejects missing or ambiguous files.
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
- Registration diagnostics expose the applied profile and validator provenance;
  `GET /api/v1/schemas/{version}` serves the exact bundled adapter schema.

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
**I need** to register my adapter repository using my verified GitHub identity
**So that** valid metadata is published with an accountable owner

##### Details and Assumptions
- Web and CLI publishing use a public HTTPS repository with root-level metadata.
- Adapter identity/name come from metadata; ownership comes from authentication.
- Retrieval, validation and acceptance complete in one operation.

##### Acceptance Criteria

```gherkin
Given an authenticated maintainer provides a repository with valid metadata
When registration completes
Then the accepted adapter is published for the verified account
```

---

#### US-04a Registration UI and submission persistence

**As an** adapter maintainer
**I need** live validation feedback when registering my repository
**So that** I can understand failures and correct the metadata

##### Details and Assumptions
- Browser and CLI use the same registration service and acceptance rules.
- Progress reports file retrieval, Croissant, profile, semantics and dataset checks.
- Publication is confirmed by the terminal result after persistence.

##### Acceptance Criteria

```gherkin
Given an authenticated maintainer submits a repository
When its metadata passes validation and acceptance
Then the source, canonical entry and success event are committed together
And the interface reports the published version

Given the final result is lost after a connection interruption
When the interface cannot confirm publication
Then it reports an unconfirmed outcome without automatically resubmitting
```

---

#### US-05 Persist valid adapter records

**As a** registry system maintainer
**I need** only accepted metadata to become canonical registry entries
**So that** consumers can query validated metadata reliably

##### Details and Assumptions
- SQLite and PostgreSQL implement the same persistence port.
- Accepted metadata and the latest attempt outcome are separate concepts.

##### Acceptance Criteria

```gherkin
Given adapter metadata passes validation and acceptance rules
When registration finishes
Then its canonical entry is persisted with a current source pointer
And a successful processing event is recorded
```

---

#### US-06 Prevent duplicates

**As a** registry system maintainer
**I need** adapter identity/version uniqueness and consistent source ownership
**So that** the catalog remains canonical under concurrent registration

##### Details and Assumptions
- Canonical keys use normalized adapter identity and metadata version.
- Missing metadata @id falls back consistently to the metadata name.
- Repository locations and canonical identity/version keys are unique.
- New sources/versions cannot claim another account's adapter identity.

##### Acceptance Criteria

```gherkin
Given an accepted adapter identity and version
When another repository submits the same key
Then the duplicate is rejected without creating its source or failure event

Given competing accounts register versions of the same adapter identity
When their transactions overlap
Then only one account can become its owner
```

---

#### US-06a Registration database architecture and event history

**As a** registry system maintainer
**I need** accepted sources, canonical entries and processing history separated
**So that** publication remains atomic and failed updates are auditable

##### Details and Assumptions
- Core tables are `registration_sources`, `registry_entries` and `registration_events`.
- Accepted first registrations create all three atomically; rejected first attempts create none.
- Updates append terminal events while retaining accepted metadata on failure.
- Checksums avoid replacing unchanged metadata; version labels are arbitrary strings.
- Fresh SQLite/PostgreSQL databases use the current schema without legacy upgrades.

##### Acceptance Criteria

```gherkin
Given valid first-registration metadata
When acceptance commits
Then its source points to the canonical entry and a VALID_CREATED event exists

Given a published adapter is updated without metadata changes
When processing completes
Then the canonical entry is unchanged and an UNCHANGED event is appended

Given invalid first-registration metadata
When registration is rejected
Then no source, canonical entry or attempt event is saved
```

---

#### US-07 Actionable validation errors and update history

**As an** adapter maintainer
**I need** precise validation diagnostics
**So that** I can correct repository metadata and retry

##### Details and Assumptions
- Failed first attempts return errors without storing registration records.
- Failed published updates retain accepted metadata and record their attempt.
- Diagnostics include available field paths, file positions and requirements.

##### Acceptance Criteria

```gherkin
Given unregistered metadata is missing a required version
When registration finishes
Then the terminal attempt fails with version diagnostics
And no source, entry or failure event is saved

Given an already published adapter has an invalid update
When the update finishes
Then its published metadata is retained and the failed attempt is recorded
```

---

#### US-08 Non-blocking batch refresh

**As a** registry system maintainer
**I need** independent processing of published active sources
**So that** one retrieval or validation failure does not stop the batch

##### Details and Assumptions
- Batch refresh is invoked manually through the existing CLI.
- It preserves accepted metadata on failures and records each source's outcome.
- A persisted run summary distinguishes fetch failures from internal errors.
- Automatic scheduling, backoff and a web batch trigger are not implemented.

##### Acceptance Criteria

```gherkin
Given published sources have unchanged, invalid and unavailable candidates
When batch refresh runs
Then every source is processed independently
And failures are recorded while accepted metadata is retained
And the run summary reports the mixed outcomes

Given failed update metadata is corrected before another batch
When batch refresh runs again
Then the corrected candidate can be published under the normal acceptance rules
```

---

#### US-09 On-demand retries and adapter updates

**As an** adapter maintainer
**I need** immediate retries after correcting metadata
**So that** I do not need a scheduled run

##### Details and Assumptions
- A failed first registration is retried by submitting the repository again.
- Published adapters are retried through Update, owned by the submitting account.
- Changed published metadata retains identity and uses a different, unused label;
  semantic-version ordering is not required.
- Unchanged metadata succeeds; forced validation is available in the CLI.

##### Acceptance Criteria

```gherkin
Given a first registration failed validation
When the maintainer corrects metadata and retries with the same version
Then the valid adapter can be registered

Given a published adapter has a failed candidate update
When its owner corrects metadata and repeats Update
Then the corrected version is published and history remains consistent
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
**I need** a persisted summary of each completed batch refresh
**So that** I can review throughput and failures

##### Details and Assumptions
- Each summary has a run identifier and start/finish timestamps.
- Counters cover active/processed sources, accepted/unchanged/invalid candidates,
  duplicates, version conflicts, fetch failures and internal failures.
- The CLI and read-only API expose the last completed summary.

##### Acceptance Criteria

```gherkin
Given a completed batch refresh
When its latest summary is requested
Then the run identifier, timestamps and outcome counters are returned
And internal errors are distinguished from retrieval failures
```

---

#### US-12 React front-end migration

**As a** registry system maintainer
**I need** a professional front-end built with React to replace the existing front-end responsibilities
**So that** the project has a maintainable user experience layer that reuses
current backend logic through the FastAPI contract

##### Details and Assumptions
- The React application owns the current browser workflows.
- Existing backend business logic should remain reusable and should not be reimplemented in the front-end.
- Front-end to backend communication uses generated clients from the FastAPI
  OpenAPI document.
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

Given the FastAPI contract changes
When the checked-in OpenAPI document and TypeScript client are regenerated
Then the React front-end can adopt the change through its explicit API boundary
Without duplicating backend business rules
```

### Check gate
- [x] Create GitHub issue cards for these user stories.

---
