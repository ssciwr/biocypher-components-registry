# Current Generation Implementation Status

This document reflects the current repository state after the feature-oriented refactor.

## Summary

The repository no longer uses the old `generation/` and `generators/` implementation layout.

The active implementation now lives in:

- [`src/core/adapter`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/adapter)
- [`src/core/dataset`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/dataset)
- [`src/core/web`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/web)
- [`src/core/shared`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/shared)
- [`src/core/validation`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/validation)

The codebase is now organized by feature:

- `adapter/`: adapter requests, config parsing, CLI, backend, and document building
- `dataset/`: dataset requests, config parsing, CLI, inference, backends, formats, and document building
- `web/`: web server, form mapping, and page rendering
- `shared/`: constants, errors, creator parsing, IDs, licenses, and discovery/file helpers

## Status Table

| Objective | Status | Current evidence | Notes |
|---|---|---|---|
| Separate workflow from backend implementation | Implemented | [`src/core/adapter/cli.py`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/adapter/cli.py), [`src/core/dataset/cli.py`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/dataset/cli.py), [`src/core/adapter/service.py`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/adapter/service.py), [`src/core/dataset/service.py`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/dataset/service.py) | CLI and web interfaces now delegate to feature services and request builders. |
| Support authoring modes `guided`, `config`, and `direct` | Implemented | [`src/core/adapter/cli.py`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/adapter/cli.py), [`src/core/dataset/cli.py`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/dataset/cli.py) | Both adapter and dataset commands expose the three modes directly from their feature package. |
| Keep final adapter assembly in native repo code | Implemented | [`src/core/adapter/backends/native.py`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/adapter/backends/native.py) | Adapter final generation is still native-only. |
| Allow dataset generation to use interchangeable backends | Implemented | [`src/core/dataset/backends/__init__.py`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/dataset/backends/__init__.py) | Dataset backends are resolved through the dataset feature package. |
| Native dataset backend | Implemented | [`src/core/dataset/backends/native.py`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/dataset/backends/native.py) | Handles file discovery, format inspection, document construction, and validation. |
| External `croissant-baker` dataset backend | Implemented | [`src/core/dataset/backends/croissant_baker.py`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/dataset/backends/croissant_baker.py) | Still subprocess-backed. |
| Explicit backend selection in CLI | Implemented | [`src/core/dataset/cli.py`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/dataset/cli.py), [`src/core/adapter/cli.py`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/adapter/cli.py) | Dataset commands use `--generator`; adapter commands use `--dataset-generator`. |
| `auto` backend/provider selection | Implemented | [`src/core/dataset/backends/auto_select.py`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/dataset/backends/auto_select.py) | `auto` currently applies a baker-first policy with `.tsv.gz` fallback to native. |
| Local inference available in the active stack | Implemented | [`src/core/dataset/inference.py`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/dataset/inference.py), [`src/core/web/server.py`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/web/server.py) | Inference is shared by dataset and web flows, but still not exposed as a separate backend named `local`. |
| Preconfigured dataset generation from YAML | Implemented | [`src/core/dataset/config.py`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/dataset/config.py) | YAML is normalized into `GenerationRequest`. |
| Preconfigured adapter generation from YAML | Implemented | [`src/core/adapter/config.py`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/adapter/config.py) | Supports existing datasets and generated datasets. |
| Hybrid adapter workflows combining existing and generated datasets | Implemented | [`src/core/adapter/cli.py`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/adapter/cli.py), [`src/core/adapter/backends/native.py`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/adapter/backends/native.py) | `adapter direct` supports existing datasets, dataset config files, and inline repeatable `--dataset` blocks. |
| Review/correction in guided flows | Implemented | [`src/core/adapter/cli.py`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/adapter/cli.py), [`src/core/dataset/cli.py`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/dataset/cli.py) | Guided flows support review and retry before execution. |
| Web UI aligned with the active generation stack | Implemented | [`src/core/web/server.py`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/web/server.py), [`src/core/web/forms.py`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/web/forms.py), [`src/core/web/pages.py`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/web/pages.py) | The web UI now uses the same adapter/dataset request and execution stack as the CLI. |
| Legacy generation fully replaced by the new stack | Implemented | [`cli.py`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/cli.py), [`src/core/adapter`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/adapter), [`src/core/dataset`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/dataset), [`src/core/web`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/web) | The old `generation/`, `generators/`, `validation_new/`, `validator.py`, `builder.py`, `cli_wizard.py`, and legacy web modules were removed. |
| Prefer `croissant-baker` Python API over subprocess integration | Not implemented | [`src/core/dataset/backends/croissant_baker.py`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/dataset/backends/croissant_baker.py) | The current implementation still shells out to the executable. |
| Typed creator objects end to end | Not implemented | [`src/core/adapter/request.py`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/adapter/request.py), [`src/core/dataset/request.py`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/dataset/request.py) | Creator handling is cleaner than before, but request models still store creator values as strings. |

## Active Layout

```text
src/core/
  adapter/
  dataset/
  web/
  shared/
  validation/
  schema/
```

## What Was Removed

These implementation areas are no longer part of the active stack:

- `src/core/generation/`
- `src/core/generators/`
- `src/core/validation_new/`
- `src/core/validator.py`
- `src/core/constants.py`
- `src/core/exceptions.py`
- `src/core/discovery.py`

## Remaining Follow-Up

The most useful remaining follow-up items are:

1. move creators from string-based request fields to typed value objects
2. document the feature-oriented layout in README and architecture notes
3. decide whether `croissant-baker` should remain subprocess-based or move behind a richer integration layer
