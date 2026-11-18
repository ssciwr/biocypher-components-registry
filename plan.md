# Support editing multiple files within one dataset

## Agreed plan

Extend the existing editor so folder-generated metadata exposes every file and table. For STITCH, retain one shared dataset description and allow editing Actions and Detailed links independently.

1. Use the existing distributions and record sets arrays as the authoritative editing state after generation or import. Reuse the uploaded-Croissant resource editors and merge logic.
2. Show independent distribution and record-set selectors when multiple resources exist. Display filenames, field counts and source references. Keep computed file metadata read-only for generated resources.
3. Persist edits when switching selections and export changes to the corresponding resource. Preserve identifiers, source references, Baker datatypes and properties outside the form.
4. Keep dataset name, description, citation, creators, version, publication date, landing page and license shared.
5. Verify single-file, generated multi-file and uploaded multi-resource workflows, including second-resource edits, field changes and file exclusion.

## Boundaries

One folder-generation request still produces one dataset description. Automatic splitting into separate datasets is deferred. No Baker, backend API or Croissant vocabulary changes are planned. Licensing and provenance discrepancies remain discussion items.

## Acceptance criteria

- All generated distributions and record sets are selectable and editable.
- Switching selections and exporting preserves edits to each resource independently.
- New fields reference their own table's source when it is unambiguous.
- Single-file editing remains simple, and uploaded documents retain existing behavior.
- Unchecked files are excluded before generation; an empty inclusion is rejected.
- Frontend tests, lint and production build pass, with browser verification of the folder workflow and validation of a representative export.

## Handoff — 2026-11-18

### Repository and implementation status

- Platform repository: `biocypher-components-registry` (current local path `/home/ecarreno/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry`).
- Branch: `fix/upload-dataset-croissant-mech`.
- Latest commit at handoff: `4849878` (`improve multifile use case selection`). Previous commit: `4bba596` (`Improve adapter metadata classification and dataset editing`). The working tree was clean before adding these handoff notes.
- Phase described above is implemented: generated metadata exposes all distributions and record sets, supports independent selections, and exports edits using the shared merge logic.
- File inclusion checkboxes were also implemented. Unchecked files remain visible for reselection but are excluded before format validation, hashing, upload and generation. At least one file must remain included.
- Dataset metadata stays shared. Folder generation does not automatically create a separate dataset per file. This behavior is deliberate.
- Generated filenames, formats and checksums remain read-only; uploaded metadata retains its existing editing behavior.
- New fields infer a source from their own table only when a single source is identifiable. Empty or multi-source tables do not default to the first distribution.

Relevant implementation and regression coverage:

- `frontend/src/pages/createMetadata/MetadataGeneratorFields.tsx`: source checklist, distribution editor, independent resource selectors.
- `frontend/src/pages/CreateAdapterMetadataPage.tsx`: selected-resource state updates.
- `frontend/src/pages/createMetadata/utils.ts`: projection, shared resource merging and export.
- `frontend/src/pages/createMetadata/generatedResources.test.tsx`: generated resource editing and export tests.
- `frontend/cypress/e2e/create-adapter-metadata-editing.cy.ts`: browser verification of switching resources, second-table changes and export.

### Verification already completed

- All 92 frontend unit tests passed (`npm test` from `frontend/`).
- All 10 browser tests in `create-adapter-metadata-editing.cy.ts` passed, including the generated two-file workflow.
- Frontend lint and production build passed. Build reported the existing large-chunk warning.
- A representative combined STITCH export passed the platform's adapter validator.
- The actual two metadata files listed below were subsequently validated independently; both passed complete-file compatibility, adapter schema, adapter semantics and embedded dataset checks.
- No source TSV files were downloaded or rehashed during the final comparison. Matching hashes below are comparisons of stored metadata values, not a new integrity verification.

Browser environment note: Cypress initially failed because `ELECTRON_RUN_AS_NODE` was set. Running with `env -u ELECTRON_RUN_AS_NODE npm run ui-tests -- --spec cypress/e2e/create-adapter-metadata-editing.cy.ts --config baseUrl=http://127.0.0.1:5174` worked against a temporary Vite server. That server was stopped after testing; use the actual available local port on the next computer.

### STITCH artifacts reviewed

These files live in the separate MetaLinks checkout, not in this platform repository:

`/home/ecarreno/SSC-Projects/b_REPOSITORIES/org_biocypher/metalinks/metalinks/metadata/`

| File | Structure | Validation |
| --- | --- | --- |
| `stitch_croissant.jsonld` | One adapter; two dataset descriptions, each with one distribution and one record set | PASS |
| `stitch_croissant_after-frontend.jsonld` | One adapter; one shared STITCH dataset with two distributions and two record sets | PASS |

The directory contained these two JSON-LD files, not the source TSVs. Ensure both files are available on the next computer; they are not transferred by committing this plan in the platform repository.

The adapter-level properties and JSON-LD context are identical between these artifacts. For each source filename, field names, datatypes, source column names, content sizes and SHA-256 values match. All field-to-file references resolve within their respective documents.

| Resource | Fields | Datatypes |
| --- | --- | --- |
| `9606.actions.v5.0.tsv` | `item_id_a`, `item_id_b`, `mode`, `action`, `a_is_acting`, `score` | First five `sc:Text`; `score` is `cr:Int64` |
| `9606.protein_chemical.links.detailed.v5.0.tsv` | `chemical`, `protein`, `experimental`, `prediction`, `database`, `textmining`, `combined_score` | First two `sc:Text`; remaining five `cr:Int64` |

The new export successfully saved record-set names `stitch-actions-human` and `stitch-protein_chemical_links_detailed-human`. Their identifiers remain distinct from their editable names, with consistent references. Do not rewrite identifiers merely to match renamed tables.

### Findings requiring follow-up

Validation confirms structural compatibility, not factual correctness or remote retrievability.

| Finding | Current frontend export | Suggested action |
| --- | --- | --- |
| Detailed-links download location is incomplete | `contentUrl` is only `9606.protein_chemical.links.detailed.v5.0.tsv`; no containing archive is declared | Enter the full Zenodo URL below in the second distribution editor, regenerate and verify the saved output |
| Publication date reflects generation day | `2026-11-18T00:00:00Z` | For the archived-snapshot description, use `2023-11-23` and explain that it is the Zenodo archive date, not the original STITCH release date |
| Citation is generic | `STITCH. (2026). STITCH [Data set].` | Restore the STITCH 5 publication citation available in the earlier metadata file; DOI `10.1093/nar/gkv1277` |
| Creator category is inaccurate | `sc:Person` named `STITCH` | Use an organization; the earlier file uses `STITCH Consortium` |
| Dataset description is generic | `Dataset containing 2 files (text/tab-separated-values) with automatically inferred types and structure` | Describe human STITCH v5 actions and detailed evidence tables and identify Zenodo as the archive location |
| Dataset license discrepancy remains unresolved | Shared CC BY 4.0 URL; earlier file uses CC-BY-4.0 for both dataset entries | Discuss applicability before publication. Earlier investigation found different licensing information for detailed links on the STITCH site; a shared dataset license must not conceal this discrepancy |
| Placeholder identifier base | Both files contain `@base: cr_base_iri/` | Agree on a deliberate base/identifier strategy before publication |
| Auxiliary inputs are not machine-readable | HMDB and Ensembl-to-UniProt mappings via pypath appear only in adapter prose | Address separately when metadata is extended to drive all adapter dependencies |
| Software license conflict | Metadata uses GPL-3.0; repository LICENSE contains GPL while pyproject.toml declares MIT | Ask maintainers to reconcile declarations; do not silently choose a different license |

The earlier file has richer descriptions and a full STITCH publication citation; use it as a reference rather than re-entering information from memory. The older file's descriptions claim equivalence to the original STITCH downloads; that claim was not reverified in this comparison.

Correct download URLs:

```text
https://zenodo.org/records/10200150/files/9606.actions.v5.0.tsv?download=1
https://zenodo.org/records/10200150/files/9606.protein_chemical.links.detailed.v5.0.tsv?download=1
```

Original dataset landing page: `https://stitch-db.org/cgi/download.pl?species_text=Homo+sapiens`.
Archive record: `https://zenodo.org/records/10200150`.

### Recommended next steps for a new session

1. Read this plan and inspect the current branch and working tree before making changes. Do not repeat the multi-resource implementation.
2. Locate both MetaLinks metadata files on the new computer and confirm their contents have not changed since this review.
3. Correct the straightforward dataset metadata through the frontend, especially the second distribution's download URL. Leave license/provenance decisions requiring discussion open.
4. Regenerate and compare both distributions and record sets, then validate the new export:

   ```bash
   .venv/bin/python cli.py validate-adapter /path/to/metalinks/metalinks/metadata/stitch_croissant_after-frontend.jsonld
   ```

5. The missing URL alone does not prove an export bug: its value may never have been edited. If a corrected second URL disappears after saving/exporting, reproduce that precise workflow and investigate; browser regression coverage already verifies that editing a second distribution can survive export.
6. Separately consider better handling of generated defaults (date, creator, citation and description) and incomplete download locations. Analyze their origin and propose changes before implementation; these enhancements are not yet implemented or authorized as part of the completed editor fix.

The user prefers simple interfaces and standards-compatible Croissant metadata. Do not automatically equate files with datasets, invent new categories, decide unresolved licenses, or introduce pipeline creation into this adapter-only frontend.
