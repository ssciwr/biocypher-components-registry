# Dataset Generation Architecture

This document focuses on the current dataset-generation implementation.

It reflects the active codebase:

- `guided`, `config`, and `direct` are user-facing modes in [`src/core/dataset/cli.py`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/dataset/cli.py)
- normalized dataset requests live in [`src/core/dataset/request.py`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/dataset/request.py)
- orchestration lives in [`src/core/dataset/service.py`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/dataset/service.py)
- backend implementations live under [`src/core/dataset/backends/`](/home/edwin/SSC-Projects/b_REPOSITORIES/org_ssciwr/biocypher-components-registry/src/core/dataset/backends)

## 1. Current Architecture

```mermaid
flowchart TB
    user[User]

    subgraph Presentation["Presentation"]
        cli["cli.py"]
        dataset_cli["src/core/dataset/cli.py"]
    end

    subgraph DatasetFeature["Dataset Feature Package"]
        config["config.py"]
        service["service.py"]
        request["request.py"]
        inference["inference.py"]
        document["document.py"]
        backends["backends/"]
        formats["formats/"]
    end

    subgraph External["External Tooling"]
        baker["croissant-baker"]
    end

    subgraph Output["Output"]
        dataset_jsonld["Dataset Croissant JSON-LD"]
    end

    user --> cli
    cli --> dataset_cli
    dataset_cli --> config
    dataset_cli --> service
    config --> request
    service --> request
    service --> backends
    backends --> formats
    backends --> document
    backends --> baker
    backends --> dataset_jsonld
```

## 2. Backend View

```mermaid
flowchart LR
    request["GenerationRequest"]

    subgraph Backends["src/core/dataset/backends/"]
        auto["auto_select.py"]
        native["native.py"]
        baker["croissant_baker.py"]
    end

    subgraph Support["src/core/dataset/"]
        formats["formats/*"]
        inference["inference.py"]
        document["document.py"]
    end

    request --> auto
    request --> native
    request --> baker
    native --> formats
    native --> document
    auto --> native
    auto --> baker
    inference --> document
```

### Interpretation

- `direct`, `guided`, and `config` differ in how they build a request.
- all modes converge on the same `GenerationRequest`
- `service.py` validates backend names and dispatches execution
- `auto_select.py` is a backend-selection policy, not a separate user flow
- `native.py` owns local discovery, format inspection, and document building
- `croissant_baker.py` owns subprocess integration with the external executable

## 3. Runtime Flow

```mermaid
sequenceDiagram
    actor User
    participant CLI as cli.py
    participant DatasetCLI as src/core/dataset/cli.py
    participant Config as src/core/dataset/config.py
    participant Service as src/core/dataset/service.py
    participant Backend as src/core/dataset/backends/*
    participant Baker as croissant-baker

    User->>CLI: dataset direct/config/guided ...
    CLI->>DatasetCLI: route command
    DatasetCLI->>Config: build request when needed
    DatasetCLI->>Service: execute_request(request, generator)
    Service->>Backend: resolve backend
    Backend-->>Service: generate(request)
    Backend->>Baker: subprocess only for croissant-baker backend
    Service-->>DatasetCLI: GenerationResult
    DatasetCLI-->>User: status + output path
```

## 4. Current Module Mapping

```mermaid
flowchart TB
    cli["cli.py"]
    dataset_cli["src/core/dataset/cli.py"]
    dataset_config["src/core/dataset/config.py"]
    dataset_service["src/core/dataset/service.py"]
    dataset_backends["src/core/dataset/backends/"]
    dataset_formats["src/core/dataset/formats/"]
    tests_cli["tests/unit/core/dataset/test_dataset_cli.py"]
    tests_guided["tests/unit/core/dataset/test_dataset_guided_cli.py"]
    tests_backends["tests/unit/core/dataset/test_backends.py"]
    tests_formats["tests/unit/core/dataset/test_formats.py"]

    cli --> dataset_cli
    dataset_cli --> dataset_config
    dataset_cli --> dataset_service
    dataset_service --> dataset_backends
    dataset_backends --> dataset_formats

    tests_cli --> dataset_cli
    tests_guided --> dataset_cli
    tests_backends --> dataset_backends
    tests_formats --> dataset_formats
```

## 5. Main Architectural Rule

The clean rule for dataset generation is:

- `cli.py` owns command registration
- `src/core/dataset/cli.py` owns the user interaction
- `src/core/dataset/config.py` owns config-to-request mapping
- `src/core/dataset/service.py` owns backend dispatch
- `src/core/dataset/backends/` own generation behavior
- `src/core/dataset/formats/` own file inspection
- `src/core/dataset/document.py` owns Croissant document construction

That keeps dataset generation understandable for both users and maintainers, while still allowing backend growth over time.
