# Raw requirements

This document collect all the vague and raw ideas we have about the project. Because they are too vague, do not follow a format and systematically combines constraints with goals they cannot be
considered proper requirements.

---

## [date] 30.06.2025

### Description of the workflow.

1. Adapter maintainers must include a single croissant.jsonld file describing the adapter metadata in each adapter repository.
    - Reviewed by human: Yes

2. Users may generate this metadata file through a guided application that asks for required fields and outputs a valid Croissant file.
    - Reviewed by human: Yes

3. Registry maintainers define a single validation schema that all croissant.jsonld files must satisfy.
    - Reviewed by human: Yes
  
4. To register an adapter, the adapter maintainer submits the adapter repository to the registry system. The system locates croissant.jsonld and performs validation.
    - Reviewed by human: Yes

5. If validation passes, the registry system extracts metadata, stores it in the registry data store, and records status as VALID.
    - Reviewed by human: Yes

6. The registry system must prevent duplicates by uniqueness key (recommended: adapter id + version).
    - Reviewed by human: Yes

7. If validation fails, the registry system records status as INVALID and stores detailed validation errors in a status log/table.
    - Reviewed by human: Yes

8. Registration processing must be non-blocking: invalid adapters must not interrupt processing of other registered repositories.
    - Reviewed by human: Yes

9.  The system must support revalidation of previously failed adapters on demand, without waiting for the next scheduled full run.
    - Reviewed by human: Yes

10. Users can use an MCP interface to discover and retrieve adapter metadata; adapter execution is performed by client applications unless explicitly supported by the MCP runtime.
    - Reviewed by human: Yes

11. The registry system must produce a processing summary for each registration/validation run, including at least: total adapters processed, number of VALID, number of INVALID, number of duplicates detected, and number of revalidated adapters, with a timestamped run identifier.
    - Reviewed by human: Yes

12. The project should provide a professional React-based front-end that replaces the current front-end responsibilities, reuses existing backend logic, and keeps integration boundaries flexible for a future move to FastAPI or Flask.
    - Reviewed by human: Yes


### Story-to-workflow traceability

| Workflow Step | User Story |
| ------------- | ---------- |
| 1             | US-01      |
| 2             | US-02      |
| 3             | US-03      |
| 4             | US-04      |
| 5             | US-04a     |
| 6             | US-05      |
| 7             | US-06      |
| 8             | US-07      |
| 9             | US-08      |
| 10            | US-09      |
| 11            | US-10      |
| 12            | US-11      |


### Check gate
- [x] Create initial User Stories in the document a-2_user_stories.md

| User Story ID | Name of User Story                    |
| ------------- | ------------------------------------- |
| US-01         | Adapter metadata file exists          |
| US-02         | Guided metadata generation            |
| US-03         | Versioned validation profile          |
| US-04         | Repository-based adapter registration |
| US-04a        | Registration UI and submission persistence |
| US-05         | Persist valid adapter records              |
| US-06         | Prevent duplicates                         |
| US-07         | Persist invalid status and errors          |
| US-08         | Non-blocking batch registration            |
| US-09         | On-demand revalidation                     |
| US-10         | MCP metadata discovery and retrieval       |
| US-11         | Run summary reporting                      |
| US-12         | React front-end migration                  |

---
