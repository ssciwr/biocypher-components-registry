# Dataset Upload and Croissant Generation Plan

This file is the implementation memory for `fix/upload-dataset-croissant-mech`.
Update it after each implementation or verification step. Work on one phase at a
time: do not start a later phase until the current phase meets its exit criteria.

## Goal and non-negotiable behavior

- A single visible source button lets the user choose either one file or one folder.
- A source is either one dataset file or an unrestricted folder inventory capped at
  1,000 files for the web workflow.
- The web formats are UTF-8 CSV and TSV, either plain or Gzip-compressed.
- Baker-compatible `.csv.gz` and `.tsv.gz` preserve this contract:
  metadata identifies the compressed bytes while schema inference reads the
  decompressed logical table.
- Files up to and including 1 MiB are processed completely. Larger files are
  sampled in the browser using complete logical rows.
- Dataset bytes are transient. They must never reach a database, persistent Docker
  volume, browser storage, URL, or log.
- The browser computes the original file SHA-256. The server independently verifies
  the uploaded artifact SHA-256. There is no folder-level SHA.
- Croissant Baker is mandatory and primary. Auto-selection may select native only for
  a documented Baker capability gap; native remains explicitly selectable. Native is
  never used as a fallback after a Baker runtime failure.
- The native and Baker implementations remain independent.
- Existing draft/session-resume behavior always restores form metadata. Prepared
  samples remain available while the page stays open; source reselection is
  required only after a reload or closed browser loses its `File` handles.

## Implementation status

| Phase | Status | Exit condition / evidence |
| --- | --- | --- |
| 0 — Implementation branch | Complete | Branch is `fix/upload-dataset-croissant-mech`; pre-existing changes were preserved. |
| 1 — Contracts and limits | Complete | Code constants define 1,000 files, 1 MiB artifacts, a 50 MiB session budget, CSV/TSV strategies, safe paths, and separate original/artifact SHA values. |
| 2 — Browser preparation | Complete and user-accepted | One visible source control supports file or folder selection; hashing uses a Web Worker; Papa Parse samples complete CSV/TSV rows; dataset bytes are not placed in browser storage. The refined metadata form and distribution workflow were manually reviewed and accepted on 2026-11-05. Frontend unit, lint, and build checks passed. |
| 3 — Ephemeral upload sessions | Complete and user-validated | Four raw-body session endpoints, in-memory state, atomic `.part` rename, byte/SHA verification, whole-artifact retry, resource accounting, deletion, idle cleanup, and shutdown cleanup are covered by 13 focused passing tests. The real frontend flow was manually validated on 2026-11-05. |
| 4 — RAM-only generation | Complete | The live PostgreSQL backend uses a writable 256 MiB `tmpfs` with `nosuid,nodev,noexec`, runs as a non-root user with one Uvicorn worker, and leaves scratch empty after finalization. Fail-closed storage, sanitized bounded processes, resource/diagnostic limits, timeout, and cleanup are covered by 15 focused passing tests. |
| 5 — Metadata reconciliation | Complete and user-validated | Every generated file is matched and restored to its original identity; internal artifact fields, inline samples, sampled counts, scratch values, and private URLs are removed before Croissant validation. Final JSON is bounded. Sixteen focused tests, the full 618-test backend suite, and a real 788 MB sampled TSV response were validated. |
| 6 — Compressed and folder support | Complete | `.csv.gz`/`.tsv.gz` use bounded browser decompression and recompression while preserving Baker's compressed identity contract. Mixed nested folders, zero-byte counting, 1,000/1,001 files, 1 MiB artifacts, and browser-before-server preparation are covered by passing tests. |
| 7 — Backend independence | Complete | Native has no Baker implementation imports; both public backends use bounded subprocesses; native Parquet is metadata-only; native Gzip identity is complete; Baker success and warning semantics are preserved while web reconciliation enforces its declared inventory; auto remains honestly Baker-first. Full backend and frontend verification passes. |
| 8 — Bounded admission and asynchronous generation | Complete | Session creation atomically reserves each prepared artifact's declared bytes under a 110 MiB aggregate budget and a 100-session cap; no backend waiting queue holds browser work. One asynchronous worker serializes generation, while `429` plus `Retry-After` lets the browser retry the unchanged prepared request. |
| 9 — heiCLOUD capacity hardening | Load test implemented; live VM validation pending | Keep one generator on `m1.small`; run the real upload protocol externally with 10, 100, and 103 Locust users while observing Docker/host memory, swap, and tmpfs. Change only a limit that measurements prove unsafe. |

## Workflow refinements

- **2026-11-08 — Lossless multi-record-set editing:** Uploaded Croissant
  datasets now project every declared record set instead of silently showing
  only the first. A compact selector identifies each record set with its field
  count and source FileObject/FileSet. Field and record-set-name edits are scoped
  to the selection while preserving sibling record sets, record-set and field
  `@id` values, extraction columns, file references, and unknown properties.
  The CASMI26 example exposes all 10 record sets and 159 fields independently.
  Nine frontend test files (41 tests), lint, and the production build pass.
- **2026-11-08 — Lossless multi-distribution editing:** Uploaded Croissant
  datasets now expose a compact selector for every declared distribution and
  allow editing its content URL, filename, encoding format, SHA-256, and MD5.
  Contained files are identified as paths within their archive. Edits preserve
  sibling distributions, `@id`, `containedIn`, size, description, and unknown
  properties. Checksums are optional, SHA-256 is presented as preferred, and
  existing MD5 representations are preserved without imposing validation rules
  stricter than `mlcroissant`. Nine frontend test files (40 tests), lint, and the
  production build pass.
- **2026-11-08 — Lossless uploaded field editing:** Field entries from the first
  uploaded Croissant record set are editable during dataset review. Column name,
  datatype, description, examples, removal, and manual additions are patched
  without reconstructing unrelated field or record-set properties. When an
  original field name and extraction column are identical (or both empty), a
  column-name edit keeps them aligned while preserving the field `@id` and file
  reference. Nine frontend test files (39 tests), lint, and the production build
  pass. Multiple record-set selection and multi-distribution editing remain
  separate checkpoints.
- **2026-11-08 — Creator editing and silent-state audit:** Dataset creators are
  now editable from the dataset review step in both generated and uploaded
  workflows. Uploaded top-level metadata remains editable there while only its
  distribution and record-set structure stays read-only. Editing a creator now
  preserves original values the form cannot represent, and selecting a new
  uploaded Croissant file no longer inherits missing metadata or creators from
  the previous draft. Duplicate Basic/Details editors were removed while editing
  an existing dataset. Nine frontend test files (38 tests), lint, and the
  production build pass; a focused Cypress interaction was added, although the
  local Cypress binary exited with code 132 before executing in the current
  environment.
- **2026-11-08 — Lossless uploaded top-level and creator editing:** After an
  existing Croissant JSON-LD file is selected, its supported top-level metadata
  and creators are immediately editable in the existing dataset form. Only
  explicitly changed properties are patched into the authoritative document:
  unchanged structured licenses and full timestamps retain their original JSON
  values, numeric versions retain their type, and unsupported creator properties
  remain intact. Distribution and record-set editing deliberately remain
  disabled for their separate checkpoints. Nine frontend test files (36 tests),
  lint, and the production build pass.
- **2026-11-08 — Uploaded creator projection:** Uploaded Croissant creator objects
  now project into the existing Dataset creators draft model without enabling
  editing yet. Singleton and array forms, Person/Organization type, name, email,
  URL, compatible affiliations, and ORCID identifiers are mapped. Each projected
  creator retains its original array position for later lossless patching, while
  unsupported properties such as the Social Sentiment creator image remain only
  in the authoritative JSON-LD and are not invented as form fields. Nine frontend
  test files (34 tests), lint, and the production build pass.
- **2026-11-08 — Uploaded top-level metadata projection:** Added a read-only
  projection layer for the existing dataset form without enabling uploaded-file
  editing yet. The Social Sentiment example now projects its numeric version as
  visible text while retaining the authoritative numeric JSON value, represents
  its structured CC0 license with both name and URL, retains the complete
  description beyond 500 characters, and maps its name, landing page, full
  DateTime, and citation. Unsupported language-tagged objects are preserved but
  not flattened into misleading text. Generation-mode license precedence remains
  unchanged. Nine frontend test files (32 tests), lint, and the production build
  pass.
- **2026-11-08 — Lossless uploaded-document edit foundation:** Added an
  immutable, path-based Croissant JSON-LD update mechanism without enabling the
  uploaded-file form yet. Focused tests based on the Social Sentiment document
  prove that an unchanged document remains structurally identical, one explicit
  edit changes only its target, unsupported creator properties survive nested
  edits, sibling distributions and containment relationships remain intact, and
  removal occurs only when explicitly requested. Eight frontend test files (27
  tests), lint, and the production build pass.
- **2026-11-08 — Shared validation-results visual hierarchy:** Create and Register
  now use one stacked, responsive validation report rather than a compressed
  three-column table. The result hero uses the same status-icon pattern in both
  workflows; adapter checks remain compact, embedded datasets are visibly nested,
  and failed checks open automatically. Passed details remain collapsed, one
  expand/collapse control governs progressive disclosure, and meaningful labels
  no longer use extra-small type. `mlcroissant` messages remain authoritative and
  unchanged; URI alternatives joined by `or` are only reformatted as a readable
  monospace list. Seven frontend test files (21 tests), lint, and the production
  build pass.
- **2026-11-08 — Layered adapter and dataset validation:** The adapter profile now
  validates adapter-owned structure without reinterpreting fields owned by the
  Croissant specification. Each embedded dataset is validated independently with
  `mlcroissant`, and the complete assembled adapter is validated again as an
  integration check. Findings repeated by both passes are attributed to the
  responsible dataset and displayed once. The generation result reuses the same
  icon-based, expandable validation-progress report as the Register workflow, so
  check status, validator provenance, and diagnostics have one consistent UX.
  Numeric dataset versions,
  structured licenses, and absent dataset landing URLs no longer produce stricter
  local-schema errors when `mlcroissant` accepts them. Repeated JSON-LD term
  definitions inside embedded `@context` objects are no longer mistaken for
  duplicate graph nodes. Focused validation tests (58), a direct two-dataset check
  using the supplied invalid file, frontend tests (16), lint, and the production
  build pass.
- **2026-11-07 — Complete generation validation diagnostics:** The adapter result
  now exposes the same ordered validation stages and provenance used by Register:
  Croissant compliance with the mlcroissant version, adapter schema/profile,
  registry semantics, the embedded-dataset group, and one named validation check
  per dataset. JSON Schema union summaries no longer dump the complete `hasPart`
  array; actionable leaf errors include their JSON path, requirement, expected
  format, and schema information. Seventy-four focused backend/API tests and the
  complete frontend test/lint/build checks pass.
- **2026-11-07 — Two-dataset validation report:** Adapter generation now embeds
  uploaded Croissant JSON-LD unchanged even when that document fails Croissant
  validation, allowing one adapter to contain both a browser-generated dataset and
  an existing uploaded dataset. The final screen presents adapter checks and each
  embedded dataset check in a Register-style expandable validation report with the
  original validator errors. Invalid output is clearly marked but remains
  downloadable for inspection; registration still enforces validity. Twenty-eight
  focused backend/API tests and sixteen frontend tests pass, together with frontend
  lint and the production build.
- **2026-11-07 — Lossless uploaded Croissant documents:** Existing dataset
  Croissant JSON-LD is now preserved as the authoritative document and submitted
  unchanged for backend validation. The frontend no longer reconstructs its
  distributions, record sets, fields, identifiers, datatypes, or source mappings,
  and does not impose generated-dataset version/date requirements on uploaded
  documents. Uploaded metadata remains visible in the populated details form but
  is read-only. Generated multi-file metadata preserves additional distributions
  and record sets when the form-visible section is updated. `mlcroissant` warnings
  are no longer relabelled as validation errors; the original validator error text
  is returned. The reported social-media dataset now produces only its genuine
  invalid-`extract` error. Focused frontend tests, lint, production build, and
  backend validation/adapter tests pass.
- **2026-11-07 — Standard validation context (superseded 2026-11-08):** The
  earlier removal of `equivalentProperty` was based on an incorrect interpretation
  of mlcroissant's warning. The warning lists terms missing from the supplied
  context, not extra terms. The declaration is restored in the 2026-11-08
  validation-reporting refinement below.
- **2026-11-06 — Transparent download metadata:** `contentUrl` is preserved as
  user-provided Croissant metadata. The application does not download it, infer its
  representation from its suffix, or compare its bytes with the selected source;
  Croissant Baker and mlcroissant do not provide that verification. File name,
  format, size, and SHA-256 continue to describe the source selected by the user.
  Dataset contexts retain the separately agreed Croissant 1.0 adapter contract.
- **2026-11-05 — User-accepted workflow checkpoint:** The source selector,
  dataset metadata layout, field guidance, Citation/BibTeX editor, license
  precedence, and pre-generation Distribution metadata workflow are accepted.
  Dataset download URL is the only required distribution input; generated
  technical values remain read-only. Further work continues with the backend
  phases and does not reopen this accepted UI scope unless verification finds a
  defect.
- **2026-11-05:** Added Distribution metadata to the pre-generation form.
  Dataset download URL is the only required distribution field and is preserved
  across backend generation. Encoding format, filename, and SHA-256 are visible
  as read-only values that remain empty until source processing derives them.
  Twelve frontend tests, lint, and the production build pass.
- **2026-11-05:** Corrected generated-license merge precedence. A dataset
  license explicitly selected in the frontend now survives native or Baker
  generation; a generated license is used only when the user left the field
  empty. Focused tests cover both cases. Eleven frontend tests, lint, and the
  production build pass.
- **2026-11-05:** Renamed the Adapter details license field to **Adapter
  license** and added guidance that it governs use, sharing, and modification of
  the adapter software. Dataset license guidance remains separate.
- **2026-11-05:** Renamed the ambiguous dataset `URL` form label to
  **Dataset landing page**, preserving its mapping to the Croissant dataset URL
  and its distinction from distribution-level Content URLs.
- **2026-11-05:** Renamed distribution `Content URL` to **Dataset download URL**
  in the form. Its tooltip now identifies it as the direct public URL where the
  dataset content can be retrieved; the Croissant `contentUrl` mapping is
  unchanged.
- **2026-11-05:** Refined Citation editor typography. Entered or imported
  BibTeX uses a 14 px monospace font, left alignment, and disabled spell-check;
  ordinary citation prose uses the regular 14 px interface font with
  spell-check retained. Other multiline form fields keep their original size.
  Nine frontend tests, lint, and the production build pass.
- **2026-11-05:** Added consistent help-icon guidance for source selection,
  dataset name, license, and dataset version. Guidance explains browser-only
  sampling, encourages clear titles, describes dataset licensing, and recommends
  semantic versioning without requiring it. Nine frontend tests, lint, and the
  production build pass.
- **2026-11-05:** Added compact guidance distinguishing the dataset `URL`
  (public dataset information page) from a distribution `Content URL` (the
  filename or download location of one dataset file). Frontend tests, lint, and
  production build pass.
- **2026-11-05:** Moved the dataset `URL` and distribution `Content URL`
  guidance into compact help-icon tooltips. The explanations appear on pointer
  hover and keyboard focus and remain associated with the icon for assistive
  technology. Frontend tests, lint, and the production build pass.
- **2026-11-05:** Expanded Citation into a multiline Croissant `citeAs` editor.
  Users can paste formatted text or BibTeX, or import a local UTF-8 `.bib` file.
  The browser validates and reads the file locally, then sends only its editable
  text through Baker's `--citation` mapping. Nine frontend tests, lint, and the
  production build pass.
- **2026-11-05:** Rebalanced both the initial and review dataset forms into the
  same two equal-height
  columns: URL, Dataset version, and Date published are stacked on the left;
  Citation and BibTeX import occupy the right, with the text area stretching to
  the combined left-column height. The layout collapses vertically on smaller
  screens. Nine frontend tests, lint, and the production build pass.
- **2026-11-05:** Integrated the BibTeX import action into the Citation field
  header. This keeps the action visibly attached to Citation and lets the text
  area share the left column's bottom edge instead of leaving a floating button
  below it. The compact action remains keyboard accessible and the layout wraps
  safely on narrow screens. Nine frontend tests, lint, and the production build
  pass.
- **2026-11-05:** Removed the BibTeX action from the Citation header's measured
  height. URL and Citation labels now share one baseline, their input borders
  begin at the same vertical position, and the import action remains anchored
  to the right side of the Citation header. Nine frontend tests, lint, and the
  production build pass.
- **2026-11-05:** Normalized generated JSON-LD around one shared Croissant 1.0
  context. Adapter output still declares Bioschemas ComputationalTool 1.0, while
  embedded datasets still declare Croissant 1.0; no Croissant-1.1-only terms were
  introduced. The focused
  suite passes 27 tests and `mlcroissant validate --jsonld croissant.jsonld`
  completes without the former context warning.
- **2026-11-05:** Corrected draft-session visibility. Blank forms are no longer
  stored as resumable sessions, meaningful user input enables resume, and
  choosing **Start from scratch** explicitly deletes the previous draft. Seven
  frontend unit tests, lint, and the production build pass.
- **2026-11-05:** Added `croissant_baker_frontend_mapping.xlsx`, generated from
  the Baker 0.8.x CLI contract, to audit required parameters and frontend field
  coverage. Baker's required bake inputs (`--input` and at least one named
  `--creator`) are covered; the workbook also records optional mapping gaps and
  the frontend's stricter version/date requirements. The mapping now classifies
  all 65 flags, parameters, and subcommands into nine categories and provides
  one or more usage examples for every entry.

## Phase 3 — Completed

### Scope

- Provide `POST /api/v1/metadata/upload-sessions`.
- Provide raw-body `PUT .../artifacts/{entry_id}`.
- Provide `POST .../finalize` and `DELETE .../{session_id}`.
- Keep session metadata only in process memory.
- Validate content length, received byte count, artifact SHA, and original SHA.
- Write unique `.part` files and atomically rename only verified artifacts.
- Permit retry of the complete artifact; do not implement resumable chunks.
- Enforce session/global budgets atomically.
- Remove partial and complete files on all terminal paths.
- Retain the one-worker/one-replica deployment constraint.

### Exit checklist

- [x] Endpoint contracts and no-store responses exist.
- [x] Inventory and immutable entry identities exist.
- [x] Raw request streaming and `.part` cleanup exist.
- [x] Content length, byte count, and SHA checks exist.
- [x] Session and global accounting are lock-protected.
- [x] Finalize and explicit cancellation destroy the session tree.
- [x] A failed complete upload can be retried as a whole artifact.
- [x] Shutdown removes all remaining session trees.
- [x] Phase-focused backend tests pass without hangs in an environment that permits worker threads.

### Completion evidence — 2026-11-05

- Manual browser validation through the real frontend observed the expected
  `POST upload-sessions → 201`, `PUT entry-1 → 200`, and
  `POST finalize → 200` sequence. Browser Web Worker and `hash-wasm` requests
  also confirmed client-side hashing. The user accepted Phase 3.
- A short/incomplete body fails verification, releases its reservation, removes its
  `.part` file, and returns the session to a retriable state.
- Retrying the entry sends a new complete body and succeeds; no chunk-resume state is
  retained.
- Application shutdown removes every remaining session directory.
- `tests/unit/core/dataset/upload/test_upload_contract.py` and
  `tests/unit/api/test_dataset_upload_sessions.py`: **13 passed**.
- One existing `rdflib` deprecation warning remains and is unrelated to Phase 3.
- The next active phase is Phase 4. Do not implement it in the same work step.

### Verification note

The restricted Codex sandbox prevents `asyncio.to_thread()` workers from running,
which makes these tests appear to hang at manager startup. Running the same focused
tests outside that restriction is required; this is an execution-environment issue,
not evidence of an application deadlock.

## Phase 4 — Completed

Use `/run/biocypher-upload-scratch` as a 256 MiB Docker `tmpfs`; add no named
upload volume and no upload `.env` settings. Fail closed if it is not memory-backed.
Run generators with bounded time/resources/diagnostics and a sanitized environment.
Clean scratch on success, error, cancellation, timeout, disconnect, and shutdown.

### Exit checklist

- [x] SQLite, PostgreSQL, and production Compose mount a 256 MiB upload `tmpfs`.
- [x] The API fails closed if scratch is absent, non-tmpfs, insufficiently
  restricted, or not writable.
- [x] The backend runs as non-root with one Uvicorn worker and one concurrent
  generator.
- [x] Baker and native run with a secret-free environment through `prlimit`.
- [x] Address-space, CPU, output-file, open-file, diagnostics, and wall-time
  limits are enforced.
- [x] Finalization and every terminal session path remove transient scratch.
- [x] Deployment documentation records the tmpfs swap caveat and one-worker
  constraint.

### Completion evidence — 2026-11-05

- The live PostgreSQL container reported `tmpfs` with
  `rw,nosuid,nodev,noexec,size=262144k`; the non-root `apiuser` could access it,
  and no session artifacts remained after the manually validated finalization.
- Focused upload and isolation suites: **15 passed**. Tests include fail-closed
  scratch, secret filtering, `prlimit` arguments, bounded stdout/stderr, actual
  wall-time termination, cleanup, and hidden generator failures.
- The observed 1.2-second `finalize` request is not an upload bottleneck. A real
  Baker 0.8.0 run on a tiny CSV took about 0.66 seconds, while application
  validation averaged about 0.004 seconds. Remaining time is consistent with
  container/process startup, proxying, reconciliation, serialization, and
  transport overhead.
- One existing `rdflib` deprecation warning remains unrelated to Phase 4.

## Phase 5 — Completed

Match each generated `FileObject` by entry identity and normalized relative path.
Restore original path, name, size, content URL, and SHA. Keep artifact SHA internal.
Remove sample URLs/counts/values and scratch paths. Reject ambiguous results, run
privacy validation then Croissant validation, and return only bounded final JSON.

### Exit checklist

- [x] Every generated `FileObject` must match exactly one inventory entry.
- [x] Entry ID and normalized relative path matching support nested duplicate
  basenames without guessing.
- [x] Original name, content URL, size, encoding format, and SHA replace
  transient artifact identity.
- [x] Internal entry/artifact fields and inline sample values are removed.
- [x] Sample-derived counts are removed for sampled artifacts while legitimate
  counts from complete files are preserved.
- [x] Scratch paths, `file:` URLs, `data:` URLs, and artifact SHA values are
  rejected recursively.
- [x] Privacy reconciliation runs before Croissant validation.
- [x] Raw generator stdout and stderr are never returned.
- [x] Final metadata is rejected above the 10 MiB response limit.
- [x] Finalization cleanup removes scratch on success and failure.

### Automated verification — 2026-11-05

- Focused upload/reconciliation suites: **16 passed**.
- Full backend suite: **618 passed, 39 skipped**.
- Existing `rdflib` and websocket deprecation warnings are unrelated.

### Manual validation — 2026-11-05

- A real Croissant Baker response for a sampled 787,995,280-byte TSV returned
  one reconciled `FileObject` with the original size, a 64-character SHA-256,
  the user-provided public content URL, and valid TSV encoding metadata.
- Croissant validation returned `is_valid: true` with no errors.
- After excluding legitimate vocabulary declarations inside `@context`, the
  response contained no scratch path, local or inline-data URL, entry ID,
  artifact SHA field, inline examples, or sample values.
- The final response was 13,178 bytes, below the 10 MiB bound.
- The observed uncompressed `.tsv` versus public `.tsv.gz` identity mismatch is
  not accepted as final metadata; Baker-compatible Gzip support is explicitly
  assigned to Phase 6.
- The user accepted Phase 5. Phase 6 is next and must not reinterpret Baker's
  verified compressed-artifact behavior.

## Phase 6 — Completed

Preserve normalized paths relative to the chosen root. Count zero-byte files toward
the 1,000-file limit. Reject traversal, control characters, and path collisions.
Require the entire inventory before finalization and reconcile each file separately.

Croissant Baker 0.8.0 was verified end to end with `.tsv.gz`. Compatibility
requires:

- `name` and `contentUrl` identify the original `.tsv.gz` or `.csv.gz` file;
- `contentSize` and SHA-256 describe the compressed bytes as stored;
- `encodingFormat` preserves both the logical table media type and
  `application/gzip`;
- Baker decompresses the wrapper for field and record-set inference;
- browser preparation hashes the compressed original while performing bounded
  streaming decompression, complete-row sampling, and safe recompression for the
  transient artifact;
- reconciliation replaces transient sample identity with the original compressed
  identity and must not collapse Baker's two-value encoding format.

Browser preparation now completes before requesting an upload session. Prepared
artifacts stay only in memory, are capped at 1 MiB each and 50 MiB together, and
are uploaded sequentially after admission.

### Exit checklist

- [x] `.csv.gz` and `.tsv.gz` are recognized as Gzip-wrapped logical tables.
- [x] The compressed original is hashed without treating its bytes as UTF-8.
- [x] Bounded decompression preserves complete quoted and multiline rows.
- [x] Browser samples are safely recompressed below the 1 MiB artifact limit.
- [x] A conventional trailing line terminator does not create a synthetic row.
- [x] Original compressed name, size, SHA and dual encoding are reconciled.
- [x] Plain and compressed files coexist in nested folder inventories.
- [x] Zero-byte files count toward the 1,000-file inventory limit.
- [x] Unsafe paths, traversal, control characters and collisions remain rejected.
- [x] The complete browser preparation finishes before server session creation.
- [x] OpenAPI and generated frontend clients include the compression contract.

### Completion evidence — 2026-11-06

- Frontend unit suite: **14 passed**; ESLint and production build pass.
- Focused upload and reconciliation suites: **19 passed**.
- Full backend suite: **621 passed, 39 skipped**.
- Existing `rdflib`, websocket and Vite chunk-size warnings are unrelated.

## Later phases (do not implement yet)

### Phase 7 — Repair and prove backend independence

#### Assessment baseline — 2026-11-06

The assessment is based on the installed and locked Croissant Baker **0.8.0**, direct
runs of both backends, mixed supported/unsupported folder fixtures, compressed TSV
fixtures, and source inspection. It supersedes the earlier assumption that the native
backend was already independent.

| Area | Croissant Baker backend | Native backend |
| --- | --- | --- |
| Current role | Mandatory primary backend and the only auto-selected backend | Explicitly selectable alternative; auto does not currently select it |
| Tabular formats | CSV, TSV, spreadsheets, JSON/JSONL/FHIR, Parquet | CSV, TSV, CSV.GZ, TSV.GZ, Parquet |
| Scientific/media formats | WFDB, images, DICOM, NIfTI, GEO SOFT, HDF5, VCF/BCF, SAM/BAM/CRAM, FASTA/FASTQ | None beyond the tabular formats above |
| Compression | Gzip, Bzip2 and XZ wrappers for compatible stream handlers; archives such as ZIP/TAR are reported but not opened | Gzip only for CSV and TSV |
| Multi-file semantics | Can mark files described, linked, or referenced; for example WFDB sidecars may be valid referenced files | Treats each supported file independently |
| Execution boundary | Bounded subprocess | Bounded subprocess in the upload route, but in-process through the generic service/CLI path |
| Known correctness issue | A mixed folder can exit successfully while omitting unclaimed or failed files | Same partial-folder behavior; additionally CSV imports Baker directly |
| Known resource issue | Already uses the shared bounded process runner | Parquet currently calls `pyarrow.parquet.read_table`, which can load the complete table |
| Known metadata issue | Compressed identity is available and Phase 6 reconciliation preserves it | Direct native Gzip output omits `application/gzip` from `encodingFormat` |

Croissant Baker currently supports a strict superset of the native backend's verified
formats. Therefore there is **no truthful native-only capability rule today**. Auto
selection must remain Baker-first for all current formats; Phase 7 must not invent a
reason to route production requests to native.

The earlier independence validation was incomplete because it scanned only the native
backend/process modules. The direct dependency is in
`src/core/dataset/formats/csv.py`, which imports Baker's `CSVHandler` and
`make_source`. Future dependency tests must scan and exercise the complete native
module graph.

#### Implementation sequence

1. **Establish permanent contract tests before refactoring.**
   - Prove native CSV/TSV/Gzip generation works while imports from
     `croissant_baker` are blocked.
   - Scan the entire native dependency graph, including `formats/`, rather than a
     hand-picked file list.
   - Record current format, compression, multi-file, SHA, and process-boundary
     behavior as executable tests.

2. **Remove the native implementation dependency on Baker.**
   - Replace the native CSV use of Baker internals with a local bounded delimited
     inspector shared by CSV, TSV, CSV.GZ, and TSV.GZ.
   - Keep complete logical-row handling and deterministic type inference consistent
     across comma- and tab-delimited inputs.
   - Keep the two backends free of imports from each other's implementation modules.

3. **Correct native resource and metadata behavior.**
   - Inspect Parquet through `pyarrow.parquet.ParquetFile` schema and metadata; do
     not materialize the complete table with `read_table`.
   - Emit both the logical media type and `application/gzip` for compressed native
     distributions while hashing and sizing the stored compressed bytes.
   - Fail the native request if any selected source file is unsupported or cannot be
     described. Do not return a successful partial dataset.

4. **Preserve Baker results and enforce the web inventory separately.**
   - Request Baker's private machine-readable `--report` output inside session
     scratch.
   - Accept `described`, `linked`, and `referenced` entries as covered. This preserves
     valid multi-file formats such as WFDB and avoids unsafe extension guessing.
   - Preserve Baker's zero-exit success result. Convert `unclaimed`, `failed`,
     non-terminal entries, and diagnostics into bounded structured warnings.
   - Pass a caller-provided `--report` option through unchanged; otherwise use and
     delete a private report for structured warnings.
   - Enforce exact completeness only in the web upload reconciliation, where every
     browser-declared inventory entry must map unambiguously to a `FileObject`.
   - Delete the report on every terminal path and never return its scratch paths or
     raw diagnostics to the client.

5. **Use one bounded execution architecture.**
   - Move native's in-process construction behind a private worker-only interface.
   - Make every public entry point—upload API, service API, and CLI—invoke native via
     the same sanitized, timed, resource-limited process runner used for Baker.
   - Avoid worker recursion by ensuring only the worker calls the private native
     builder.

6. **Keep selection policy honest and deterministic.**
   - Keep `auto` mapped to Baker for every capability currently shared by the two
     backends and for Baker-only formats.
   - Keep native available through explicit selection while its independent contract
     is maintained.
   - Add a future native auto-selection rule only in the same change that adds and
     tests a real native-only capability and documents the Baker gap.
   - Never catch a Baker launch, timeout, resource, scan-coverage, validation, or
     runtime failure and retry with native.

7. **Verify before marking Phase 7 complete.**
   - Both explicit backends generate valid metadata for their documented fixtures.
   - Native succeeds with Baker imports blocked and contains no Baker dependency in
     its reachable module graph.
   - Native mixed supported/unsupported folders fail instead of succeeding partially.
   - Baker referenced sidecars remain accepted, while unclaimed/failed entries and
     diagnostics remain successful with bounded warnings.
   - Native Parquet inspection is metadata-only and native Gzip metadata is correct.
   - All public native paths use bounded subprocess isolation.
   - Forced Baker failures never invoke native; explicit backend choices never
     switch silently.
   - Focused tests and the complete frontend/backend suites pass, then this status
     table is updated with exact evidence.

#### Completion evidence — 2026-11-06

- The native CSV handler uses the shared local delimited inspector and the permanent
  dependency test scans native plus every format module for Baker imports.
- Native CSV/TSV/Gzip generation runs through the private worker; the upload API,
  service API, and CLI now share the public bounded generator path.
- Native Gzip distributions carry the logical media type and `application/gzip`;
  native Parquet uses `ParquetFile` schema/metadata instead of `read_table`.
- Native rejects a mixed supported/unsupported folder before writing output.
- Baker 0.8.0 was exercised through the real adapter: both a complete TSV folder and
  the same folder with an unclaimed auxiliary file preserve Baker's successful exit;
  the latter carries a bounded warning and its private report is removed.
- Baker scan tests accept `described`, `linked`, and `referenced` without warnings,
  and translate `unclaimed`, `failed`, non-terminal outcomes, and diagnostics into
  bounded warnings.
- Auto-selection remains Baker-first and the existing forced-failure test proves a
  Baker error never invokes native.
- Dataset-focused backend tests: **38 passed**.
- Complete backend suite: **635 passed, 39 skipped**.
- Frontend: **14 tests passed**; ESLint and the production build pass. The existing
  Vite chunk-size warning is unchanged.
- The verified capability and selection contract is documented in
  `docs/dataset_backends.md`.

### Phase 8 — Bounded admission and asynchronous generation

The deliberately process-local implementation matches the existing one-replica,
one-Uvicorn-worker deployment. Session creation atomically reserves the exact prepared
artifact sizes declared by the browser. Admission is bounded by 110 MiB of aggregate
artifact bytes and 100 active sessions. There is no server-side waiting queue: when
capacity is unavailable the API returns `429` with `Retry-After`, and the browser
retries the same in-memory prepared request without re-hashing or re-sampling. One
persistent manager-owned worker runs exactly one generator at a time.

Finalization atomically transitions a ready session into the generation queue and is
idempotent by session state. Success and failure both release scratch, byte accounting,
and its reservation immediately; at most two bounded terminal results remain briefly
available for polling. A session has 60 seconds to begin uploading and active upload
sessions expire after 10 minutes of inactivity. Status polling does not refresh those
timers. Queued generation and transient results intentionally do not survive a server
restart because their corresponding browser and tmpfs artifacts are not durable.

Completion evidence — 2026-11-08:

- Focused reservation and upload-contract suites prove atomic byte admission, release,
  a 100-session cap, whole-artifact retry, and global generation concurrency one.
- Exhausted byte or session capacity returns `429` with `Retry-After`. The browser retains its already
  prepared blobs, hashes, inventory, and form payload in memory, retries admission
  automatically, and exposes **Retry now** and **Cancel** without re-sampling.
- The generated OpenAPI client includes declared artifact sizes, asynchronous
  finalization, and session-result polling; it contains no waiting-ticket API.
- Current verification: **18 upload-core tests** and **4 upload API tests** pass;
  **47 frontend tests**, ESLint, and the production build pass. The complete
  backend suite is **643 passed, 39 skipped, 0 failed**.

### Phase 9 — heiCLOUD capacity hardening

Keep the initial `m1.small` deployment deliberately fixed at one backend replica,
one Uvicorn worker, one generator, a 256 MiB `tmpfs`, and 110 MiB of accounted
artifacts. `tests/load/locustfile.py` exercises the real create/upload/finalize/poll
protocol, including `429` retries, with one generation per virtual user. Run it
externally with 10, 100, and 103 users while observing existing Locust, Docker,
and host statistics. Accept the configuration when jobs finish, retries recover,
API p95 is below one second, memory stays below 85%, swap is not sustained, and
scratch returns to zero. Change only a limit that the target-VM measurements prove
unsafe; do not add metrics infrastructure or a second generator to this VM.

Future sampler engines remain separate work: JSONL, FASTA/FASTQ, VCF/SAM,
JSON/FHIR, Parquet, imaging, scientific formats, and archive wrappers beyond Gzip.

### Validation reporting refinement — completed 2026-11-08

- Preserve mlcroissant errors and warnings as separate API fields; warnings never
  turn an otherwise valid adapter or dataset into a failure.
- Display the validator's exact warning text in the shared validation report using
  an amber **Passed with warnings** state, expanded by default.
- Attribute findings produced by independent embedded-dataset validation to the
  corresponding dataset card and avoid repeating them on the complete-file card.
- Keep complete-file-only findings, such as a non-standard top-level JSON-LD
  context, on the complete-file check.
- Include `equivalentProperty` in newly generated Croissant 1.0 contexts so new
  files use the context expected by mlcroissant. Existing uploaded documents are
  reported, not silently rewritten.
- Verified the repository `croissant.jsonld`: it is valid, with one legacy context
  warning on the complete file and advisory missing-`citeAs` warnings on the
  independently checked embedded datasets.
- The final Croissant download is disabled when validation is incomplete or any
  adapter/embedded-dataset check has a blocking error. Advisory warnings retain the
  valid result and do not prevent download. The disabled control explains that the
  user must fix the errors and generate the adapter again.

## Final verification matrix

- 1 MiB boundary, 50 MiB session budget, and complete-row CSV/TSV sampling.
- 1,000 files accepted and 1,001 rejected.
- Original SHA and artifact SHA remain distinct.
- Duplicate basenames and nested paths remain unambiguous.
- Resource limits are atomic and every terminal path cleans scratch.
- No dataset artifact reaches a database or persistent volume.
- Upload routes fail closed without tmpfs.
- Generator subprocesses receive no application secrets.
- Baker failures never invoke native.
- Final metadata contains no sample values, artifact identities, or scratch paths.
