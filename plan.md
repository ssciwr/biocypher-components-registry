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
