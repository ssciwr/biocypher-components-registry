# Integration Architecture: BioCypher Adapter Authoring + Optional Croissant Baker Inference

This diagram shows how the two approaches can be combined while keeping this repository in control of the BioCypher-specific schema and minimizing coupling to `croissant-baker`.

## Are We Using The Best Of Both Worlds?

Yes, if we split responsibilities deliberately:

- **This repository** should own everything that is BioCypher- and adapter-specific.
- **Croissant Baker** should contribute only what it is already good at: dataset/file introspection and format-aware inference.
- The integration should happen through a **local interface plus mapper**, so your project benefits from Croissant Baker without becoming structurally dependent on it.

That gives you:

- the guided authoring UX and adapter schema from this repo
- the richer dataset inference capabilities from Croissant Baker
- a replaceable boundary if Croissant Baker changes in the future

```mermaid
flowchart TB
    user[Maintainer]

    subgraph Presentation["Presentation Layer\nOwner: This repository"]
        cli["CLI Wizard\nOwner: This repository"]
        web["Web UI\nOwner: This repository"]
    end

    subgraph App["Application Layer\nOwner: This repository"]
        orchestration["Generation Orchestrator\nOwner: This repository"]
        provider_selector["Inference Provider Selector\nOwner: This repository"]
    end

    subgraph Domain["Domain Layer\nOwner: This repository"]
        adapter_model["Adapter Metadata Model\nOwner: This repository"]
        dataset_model["Normalized Dataset Model\nOwner: This repository"]
        mapper["Inference Result Mapper\nOwner: This repository"]
        builder["BioCypher Croissant Builder\nOwner: This repository"]
        validator["BioCypher Profile Validator\nOwner: This repository"]
    end

    subgraph Integration["Integration Layer"]
        provider_api["DatasetInferenceProvider Interface\nOwner: This repository"]
        local_provider["Local Tabular Inference Provider\ninference.py\nOwner: This repository"]
        baker_provider["CroissantBakerProvider\nAnti-corruption Adapter\nOwner: This repository"]
    end

    subgraph External["External Tool\nOwner: Croissant Baker"]
        baker["croissant-baker\nOwner: Croissant Baker"]
    end

    subgraph Outputs["Outputs\nOwner: This repository"]
        croissant["Final adapter-aware\ncroissant.jsonld\nOwner: This repository"]
        warnings["Warnings / validation feedback\nOwner: This repository"]
    end

    user --> cli
    user --> web

    cli --> orchestration
    web --> orchestration

    orchestration --> adapter_model
    orchestration --> provider_selector
    provider_selector --> provider_api

    provider_api --> local_provider
    provider_api --> baker_provider

    baker_provider --> baker

    local_provider --> mapper
    baker_provider --> mapper

    mapper --> dataset_model
    adapter_model --> builder
    dataset_model --> builder

    builder --> validator
    validator --> croissant
    validator --> warnings
```

## Main Idea

- This repository remains the **system of record** for adapter metadata, schema rules, validation, and final document assembly.
- Dataset introspection is delegated to a pluggable provider interface.
- `croissant-baker` is used only through a local adapter, so changes in its internals do not leak across this codebase.

## Ownership Summary

### Owned by this repository

- User-facing workflows
- Adapter schema and validation rules
- Internal normalized model
- Builder and final output contract
- Inference provider interface
- Mapper and anti-corruption layer
- Fallback local inference

### Owned by Croissant Baker

- Dataset scanning internals
- Handler system for supported formats
- Format-specific metadata extraction logic
- Upstream implementation details and release cycle

## Responsibility Split

### This repository owns

- CLI and web authoring flows
- BioCypher adapter schema and required fields
- Normalized internal metadata model
- Final Croissant assembly
- Validation and user-facing error reporting

### Optional inference providers own

- Inspecting local data files
- Inferring distributions, record sets, and fields
- Extracting format-specific metadata

### The anti-corruption adapter does

- Calls `croissant-baker`
- Translates its output into your normalized dataset model
- Shields the rest of the application from upstream API or format changes

## Suggested Control Flow

1. User fills adapter-level information in CLI or web UI.
2. User optionally asks to infer dataset structure from local files.
3. The orchestrator selects an inference provider.
4. The provider returns raw inferred dataset metadata.
5. The mapper normalizes that metadata into your internal dataset model.
6. The builder combines:
   - adapter-level metadata from your forms
   - dataset-level metadata from the normalized model
7. The validator checks the final document against your BioCypher-specific profile.

## Design Principles

- Keep `croissant-baker` **optional**.
- Depend on a **local interface**, not its internal classes.
- Normalize all provider outputs into **one internal dataset model**.
- Build the final adapter-aware Croissant document **only inside this repository**.

## Proposed Refactoring Architecture

This proposed architecture makes the web UI and CLI reuse the same domain workflow instead of each shaping Croissant metadata in its own way.

### Goals

- Reuse the same assembly pipeline from both CLI and web UI.
- Separate presentation, transport, domain, and integration concerns.
- Introduce stable internal models for draft metadata before building final Croissant JSON-LD.
- Keep inference providers replaceable.

### Proposed Module Responsibilities

#### Presentation layer

- `cli_wizard.py`: collects user input and emits draft objects
- `web_ui.py` or split web modules: renders pages, receives HTTP requests, emits draft objects

#### Application layer

- `workflow.py`: coordinates generation, validation, saving, and provider selection

#### Domain layer

- `models.py`: draft and normalized metadata classes
- `normalization.py`: parsing, slug/id normalization, preload normalization
- `assembly.py`: converts normalized models into builder calls
- `builder.py`: creates final Croissant document dictionaries
- `validator.py`: validates final output

#### Integration layer

- `providers/base.py`: `DatasetInferenceProvider`
- `providers/local.py`: current local tabular inference
- `providers/croissant_baker.py`: adapter around `croissant-baker`
- `providers/mapper.py`: translates provider outputs into internal dataset models

### Architecture Diagram

```mermaid
flowchart TB
    user[Maintainer]

    subgraph Presentation["Presentation\nOwner: This repository"]
        cli["CLI Wizard"]
        web["Web UI"]
    end

    subgraph Application["Application\nOwner: This repository"]
        workflow["MetadataGenerationWorkflow"]
        save_service["DocumentSaveService"]
    end

    subgraph Domain["Domain\nOwner: This repository"]
        drafts["Draft Models\nAdapterDraft, DatasetDraft, ..."]
        normalization["Normalization Service"]
        assembly["Assembly Service"]
        builder["Croissant Builder"]
        validator["Profile Validator"]
    end

    subgraph Integration["Integration\nOwner: This repository"]
        provider_api["DatasetInferenceProvider"]
        local_provider["LocalInferenceProvider"]
        baker_adapter["CroissantBakerProvider"]
        mapper["Provider Result Mapper"]
    end

    subgraph External["External\nOwner: Croissant Baker"]
        baker["croissant-baker"]
    end

    output["adapter-aware croissant.jsonld"]

    user --> cli
    user --> web
    cli --> drafts
    web --> drafts
    drafts --> workflow
    workflow --> normalization
    workflow --> provider_api
    provider_api --> local_provider
    provider_api --> baker_adapter
    baker_adapter --> baker
    local_provider --> mapper
    baker_adapter --> mapper
    mapper --> normalization
    normalization --> assembly
    assembly --> builder
    builder --> validator
    validator --> save_service
    save_service --> output
```

### Class Diagram

```mermaid
classDiagram
    class MetadataGenerationWorkflow {
        +generate(draft, output_path, provider_name) dict
        +validate(doc) ValidationResult
    }

    class AdapterDraft {
        +name: str
        +description: str
        +version: str
        +license: str
        +code_repository: str
        +keywords: list[str]
        +creators: list[CreatorDraft]
        +datasets: list[DatasetDraft]
    }

    class CreatorDraft {
        +name: str
        +affiliation: str
        +identifier: str
    }

    class DatasetDraft {
        +name: str
        +description: str
        +version: str
        +license: str
        +url: str
        +date_published: str
        +cite_as: str
        +distribution: list[DistributionDraft]
        +record_sets: list[RecordSetDraft]
        +inference_request: InferenceRequest
    }

    class DistributionDraft {
        +name: str
        +content_url: str
        +encoding_format: str
        +md5: str
        +sha256: str
    }

    class RecordSetDraft {
        +name: str
        +id: str
        +fields: list[FieldDraft]
    }

    class FieldDraft {
        +name: str
        +description: str
        +data_type: str
        +examples: list[str]
    }

    class NormalizationService {
        +normalize_adapter(draft) AdapterDraft
        +normalize_dataset(draft) DatasetDraft
    }

    class AssemblyService {
        +assemble_document(draft) dict
        +assemble_dataset(dataset_draft) dict
    }

    class DatasetInferenceProvider {
        <<interface>>
        +infer(request) InferenceResult
    }

    class LocalInferenceProvider {
        +infer(request) InferenceResult
    }

    class CroissantBakerProvider {
        +infer(request) InferenceResult
    }

    class ProviderResultMapper {
        +to_dataset_draft(result) DatasetDraft
    }

    class ValidationResult {
        +is_valid: bool
        +errors: list[str]
        +profile_version: str
    }

    MetadataGenerationWorkflow --> NormalizationService
    MetadataGenerationWorkflow --> AssemblyService
    MetadataGenerationWorkflow --> DatasetInferenceProvider
    MetadataGenerationWorkflow --> ValidationResult
    AdapterDraft --> CreatorDraft
    AdapterDraft --> DatasetDraft
    DatasetDraft --> DistributionDraft
    DatasetDraft --> RecordSetDraft
    RecordSetDraft --> FieldDraft
    DatasetInferenceProvider <|.. LocalInferenceProvider
    DatasetInferenceProvider <|.. CroissantBakerProvider
    CroissantBakerProvider --> ProviderResultMapper
    LocalInferenceProvider --> ProviderResultMapper
    ProviderResultMapper --> DatasetDraft
```

### Object Diagram

```mermaid
classDiagram
    class cliDraft["cli_draft: AdapterDraft"] {
        name = "adapter_collectri"
        version = "0.1.0"
        keywords = ["transcriptomics", "regulation"]
    }

    class creator1["creator_1: CreatorDraft"] {
        name = "Edwin Carreño"
        affiliation = "..."
    }

    class dataset1["dataset_1: DatasetDraft"] {
        name = "CollecTRI"
        url = "https://..."
        inference_request = "local TSV"
    }

    class dist1["dist_1: DistributionDraft"] {
        content_url = "data/in/sample_annotations.tsv"
        encoding_format = "text/tab-separated-values"
    }

    class rs1["recordset_1: RecordSetDraft"] {
        name = "collectri records"
        id = "collectri-records"
    }

    class field1["field_1: FieldDraft"] {
        name = "source"
        data_type = "sc:Text"
    }

    class workflow1["workflow: MetadataGenerationWorkflow"]
    class provider1["provider: LocalInferenceProvider"]
    class mapper1["mapper: ProviderResultMapper"]
    class doc1["doc: Final Croissant Document"] {
        @type = "SoftwareSourceCode"
        hasPart = "[Dataset]"
    }

    cliDraft --> creator1
    cliDraft --> dataset1
    dataset1 --> dist1
    dataset1 --> rs1
    rs1 --> field1
    workflow1 --> cliDraft
    workflow1 --> provider1
    provider1 --> mapper1
    workflow1 --> doc1
```

### Interpretation

- The **architecture diagram** shows separation of concerns and ownership boundaries.
- The **class diagram** shows the stable abstractions that allow CLI and web UI to share the same workflow.
- The **object diagram** gives one concrete runtime example of how a draft created by the UI becomes a final Croissant document.

### Expected Benefits

- Less duplication between CLI and web UI.
- Easier integration of `croissant-baker`.
- Easier testing at the workflow and model level.
- Smaller and clearer `web_ui.py`.
- A cleaner path toward future providers and richer dataset inference.
