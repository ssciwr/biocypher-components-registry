# BioCypher Components Registry Diagram

This diagram summarizes the current repository structure after the feature-oriented refactor.

```mermaid
flowchart TB
    user[Maintainer / Developer]

    subgraph CLI["CLI Surface"]
        cli["cli.py"]
        dataset_cmd["dataset"]
        adapter_cmd["adapter"]
        validate_cmd["validate"]
        web_cmd["web"]
        registry_cmds["list / inspect / export"]
    end

    subgraph Features["Feature Packages"]
        adapter_pkg["src/core/adapter/"]
        dataset_pkg["src/core/dataset/"]
        web_pkg["src/core/web/"]
        shared_pkg["src/core/shared/"]
    end

    subgraph Validation["Validation"]
        validation_pkg["src/core/validation/"]
        profile["src/core/schema/profile.py"]
        schema["src/core/schema/croissant_v1.json"]
    end

    subgraph Registry["Registry Assembly"]
        adapters_yaml["adapters.yaml"]
        fetch_script["scripts/fetch_adapters.py"]
        generate_script["scripts/generate_registry.py"]
        external_repos["external_repos/*"]
        aggregated["aggregated_registry.jsonld / unified metadata"]
    end

    subgraph Outputs["Outputs"]
        adapter_jsonld["Adapter JSON-LD"]
        dataset_jsonld["Dataset JSON-LD"]
        web_output["Web-generated JSON-LD"]
    end

    user --> cli
    cli --> dataset_cmd
    cli --> adapter_cmd
    cli --> validate_cmd
    cli --> web_cmd
    cli --> registry_cmds

    dataset_cmd --> dataset_pkg
    adapter_cmd --> adapter_pkg
    web_cmd --> web_pkg
    validate_cmd --> validation_pkg
    validate_cmd --> shared_pkg

    adapter_pkg --> dataset_pkg
    adapter_pkg --> shared_pkg
    dataset_pkg --> shared_pkg
    web_pkg --> adapter_pkg
    web_pkg --> dataset_pkg
    validation_pkg --> profile
    profile --> schema

    adapter_pkg --> adapter_jsonld
    dataset_pkg --> dataset_jsonld
    web_pkg --> web_output

    adapters_yaml --> fetch_script
    fetch_script --> external_repos
    external_repos --> generate_script
    generate_script --> aggregated
    registry_cmds --> aggregated
```

## Reading The Diagram

- `cli.py` is the main entrypoint.
- `dataset` and `adapter` are the two generation-facing command groups.
- `web` launches the current web implementation from `src/core/web/`.
- `adapter/`, `dataset/`, `web/`, and `shared/` are now the active ownership boundaries.
- `validation/` remains separate and consumes documents produced by the feature packages.
- Registry assembly is still a separate flow driven by the scripts under `scripts/`.

## Main Flows

1. Users generate dataset metadata through `dataset` CLI commands or through the web UI.
2. Users generate adapter metadata through `adapter` CLI commands or through the web UI.
3. The feature packages build request objects, select backends, and generate JSON-LD.
4. Validation checks generated or discovered metadata through `src/core/validation/`.
5. Registered adapters are fetched and aggregated into a unified registry artifact.
