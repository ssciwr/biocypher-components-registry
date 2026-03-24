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

#### US-04 Repository-based adapter registration

**As an** adapter maintainer
**I need** to submit my repository to the registry
**So that** metadata can be discovered and validated automatically

##### Details and Assumptions
- Submission can be a local path or a repository URL.
- Discovery and validation are automated by the system.

##### Acceptance Criteria

```gherkin
Given a valid repository submission
When registration is triggered
Then the system discovers croissant.jsonld and runs validation
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
- The uniqueness key policy is configurable (for example `name+version`).
- A database is used to enforce this rule.

##### Acceptance Criteria

```gherkin
Given an adapter already stored with a uniqueness key
When another submission uses the same uniqueness key
Then the system rejects the new submission as duplicate
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
**I need** batch runs to continue after per-adapter failures
**So that** one bad adapter does not block all others

##### Details and Assumptions
- Failures are isolated at adapter level.
- Failed jobs and their causes are stored.

##### Acceptance Criteria

```gherkin
Given a batch with valid and invalid adapters
When one adapter fails validation
Then remaining adapters are still processed
And the run completes with mixed outcomes
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

### Check gate
- [x] Create GitHub issue cards for these user stories.

---

