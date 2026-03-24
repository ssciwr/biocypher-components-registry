# API Manual Verification With HTTPie

This checklist verifies the current FastAPI contract manually with HTTPie.

## Assumptions

- The API server is running at `http://127.0.0.1:8000`.
- Commands use HTTPie shorthand such as `:8000`.
- The API uses the default database path: `registry.sqlite3`.
- Demo files are created under `/tmp`.
- Replace placeholder values such as `<registration_id>`, `<entry_id>`, and
  `<adapter_id>` with values returned by earlier commands.

Start the API server locally:

```bash
uv run uvicorn src.api.app:app --reload
```

Or start the API server with Docker Compose:

```bash
docker compose up --build backend
```

When using Docker Compose, the development SQLite database is stored on the host
at `.docker-data/backend/registry.sqlite3` and mounted into the container as
`/app/data/registry.sqlite3`.

## 1. Health

```bash
http GET :8000/api/v1/health
```

Expected result:

- HTTP `200`
- JSON body includes `status: "ok"`
- JSON body includes `service: "biocypher-components-registry"`

## 2. Create Demo Input Files

Create a small dataset directory for metadata generation:

```bash
mkdir -p /tmp/biocypher-api-dataset-demo
printf 'id,name\n1,Alice\n2,Bob\n' > /tmp/biocypher-api-dataset-demo/people.csv
```

Create a local adapter repository with valid `croissant.jsonld`:

```bash
mkdir -p /tmp/biocypher-api-manual-adapter
cat > /tmp/biocypher-api-manual-adapter/croissant.jsonld <<'JSON'
{
  "@context": {
    "@language": "en",
    "@vocab": "https://schema.org/",
    "citeAs": "cr:citeAs",
    "column": "cr:column",
    "conformsTo": "dct:conformsTo",
    "cr": "http://mlcommons.org/croissant/",
    "dataType": {
      "@id": "cr:dataType",
      "@type": "@vocab"
    },
    "dct": "http://purl.org/dc/terms/",
    "examples": {
      "@id": "cr:examples",
      "@type": "@json"
    },
    "extract": "cr:extract",
    "field": "cr:field",
    "fileObject": "cr:fileObject",
    "recordSet": "cr:recordSet",
    "sc": "https://schema.org/",
    "source": "cr:source"
  },
  "@type": "SoftwareSourceCode",
  "@id": "manual-example-adapter",
  "name": "Manual Example Adapter",
  "description": "Adapter metadata used for manual API verification.",
  "conformsTo": "https://bioschemas.org/profiles/ComputationalTool/1.0-RELEASE/",
  "version": "1.0.0",
  "license": "https://opensource.org/licenses/MIT",
  "codeRepository": "https://example.org/manual-example-adapter",
  "programmingLanguage": "Python",
  "targetProduct": "BioCypher",
  "creator": [
    {
      "@type": "sc:Person",
      "name": "Example Creator",
      "affiliation": "Example Lab",
      "identifier": "https://orcid.org/0000-0000-0000-0000"
    }
  ],
  "keywords": [
    "adapter",
    "biocypher"
  ],
  "hasPart": [
    {
      "@type": "sc:Dataset",
      "name": "Manual Dataset",
      "description": "Small dataset embedded in the manual adapter metadata.",
      "conformsTo": "http://mlcommons.org/croissant/1.0",
      "citeAs": "https://example.org/manual-dataset",
      "creator": [
        {
          "@type": "sc:Person",
          "name": "Example Creator"
        }
      ],
      "datePublished": "2026-04-17",
      "license": "https://opensource.org/licenses/MIT",
      "url": "https://example.org/manual-dataset",
      "version": "1.0.0",
      "distribution": [
        {
          "@id": "manual-data.csv",
          "@type": "cr:FileObject",
          "name": "manual-data.csv",
          "contentUrl": "manual-data.csv",
          "encodingFormat": "text/csv",
          "sha256": "abc123"
        }
      ],
      "recordSet": [
        {
          "@id": "manual-records",
          "@type": "cr:RecordSet",
          "name": "records",
          "field": [
            {
              "@id": "manual-records/id",
              "@type": "cr:Field",
              "name": "id",
              "description": "Identifier column.",
              "dataType": "sc:Text",
              "source": {
                "fileObject": {
                  "@id": "manual-data.csv"
                },
                "extract": {
                  "column": "id"
                }
              }
            }
          ]
        }
      ]
    }
  ]
}
JSON
```

## 3. Metadata Validation

Validate inline adapter metadata from the demo repository:

```bash
http POST :8000/api/v1/metadata/validate \
  kind=adapter \
  metadata:=@/tmp/biocypher-api-manual-adapter/croissant.jsonld
```

Expected result:

- HTTP `200`
- `kind` is `adapter`
- `is_valid` should be `true` for the demo document
- `checks` includes adapter checks and embedded dataset checks

Try request validation with an unsupported kind:

```bash
http POST :8000/api/v1/metadata/validate \
  kind=unknown \
  metadata:='{"name":"Unknown"}'
```

Expected result:

- HTTP `422`

## 4. Dataset Metadata Generation

Generate dataset metadata from a server-side input path:

```bash
http POST :8000/api/v1/metadata/datasets/generate \
  input_path=/tmp/biocypher-api-dataset-demo \
  generator=native \
  validate:=true \
  name="People Demo Dataset" \
  description="Small CSV dataset used to verify generation." \
  url=https://example.org/people-demo \
  license=https://opensource.org/licenses/MIT \
  citation=https://example.org/people-demo \
  dataset_version=1.0.0 \
  date_published=2026-04-17 \
  creators:='["Person|Dataset Creator"]'
```

Expected result:

- HTTP `200`
- Response includes `metadata`
- Response includes `validation`
- `validation.is_valid` should be `true` or false with structured errors

## 5. Adapter Metadata Generation

Generate adapter metadata with one generated embedded dataset:

```bash
http POST :8000/api/v1/metadata/adapters/generate \
  name="People Adapter" \
  description="Adapter metadata generated through the API." \
  version=1.0.0 \
  license=https://opensource.org/licenses/MIT \
  code_repository=https://github.com/example/people-adapter \
  dataset_paths:='[]' \
  generated_datasets:='[
    {
      "input": "/tmp/biocypher-api-dataset-demo",
      "validate": true,
      "name": "People Dataset",
      "description": "Small people dataset.",
      "url": "https://example.org/people",
      "license": "https://opensource.org/licenses/MIT",
      "citation": "https://example.org/people",
      "dataset_version": "1.0.0",
      "date_published": "2026-04-17",
      "creators": ["Person|Dataset Creator"],
      "extra_args": []
    }
  ]' \
  validate:=true \
  creators:='["Person|Example Creator|Example Lab|||https://orcid.org/0000-0000-0000-0000"]' \
  keywords:='["adapter","biocypher"]' \
  adapter_id=people-adapter \
  programming_language=Python \
  target_product=BioCypher \
  generator=native \
  dataset_generator=native
```

Expected result:

- HTTP `200`
- Response includes adapter `metadata`
- Response includes `validation`
- Embedded dataset validation is part of the adapter validation result

## 6. Registration Workflow

Submit the local demo adapter repository:

```bash
http POST :8000/api/v1/registrations \
  adapter_name="Manual Example Adapter" \
  repository_location=/tmp/biocypher-api-manual-adapter \
  contact_email=maintainer@example.org
```

Expected result:

- HTTP `201`
- Response includes `registration_id`
- `status` is `SUBMITTED`

Save the returned `registration_id` and process it:

```bash
http POST :8000/api/v1/registrations/<registration_id>/process
```

Expected result:

- HTTP `200`
- `status` is usually `VALID` for the demo document
- Response includes validation profile/version details

Read the registration detail:

```bash
http GET :8000/api/v1/registrations/<registration_id>
```

Read the registration event history:

```bash
http GET :8000/api/v1/registrations/<registration_id>/events
```

List all active registrations:

```bash
http GET :8000/api/v1/registrations
```

## 7. Registry Operations

Run a batch refresh over all active registrations:

```bash
http POST :8000/api/v1/registry/refreshes
```

Expected result:

- HTTP `200`
- Response includes `active_sources`, `processed`, `valid_created`,
  `unchanged`, `invalid`, `duplicate`, `rejected_same_version_changed`, and
  `fetch_failed`

Read the latest refresh:

```bash
http GET :8000/api/v1/registry/refreshes/latest
```

List registry registrations:

```bash
http GET :8000/api/v1/registry/registrations
```

Filter registry registrations:

```bash
http GET :8000/api/v1/registry/registrations status==VALID
```

```bash
http GET :8000/api/v1/registry/registrations status==INVALID latest_event==INVALID_SCHEMA
```

Unsupported filter values should return `422`:

```bash
http GET :8000/api/v1/registry/registrations status==missing
```

List canonical registry entries:

```bash
http GET :8000/api/v1/registry/entries
```

Read one canonical registry entry:

```bash
http GET :8000/api/v1/registry/entries/<entry_id>
```

## 8. Adapter Catalog

List public adapters derived from canonical valid registry entries:

```bash
http GET :8000/api/v1/adapters
```

Read one adapter detail:

```bash
http GET :8000/api/v1/adapters/<adapter_id>
```

Read full metadata for one adapter version:

```bash
http GET :8000/api/v1/adapters/<adapter_id>/versions/<version>/metadata
```

For the demo document, likely values are:

```text
adapter_id = manual-example-adapter
version = 1.0.0
```

## 9. Revalidation

Revalidation is only available for registrations whose current status is
`INVALID` or whose latest event is `FETCH_FAILED`.

```bash
http POST :8000/api/v1/registrations/<registration_id>/revalidate
```

Expected result:

- HTTP `200` when the registration is eligible for revalidation
- HTTP `400` when the registration is not eligible

## 10. Cleanup

Remove demo files when they are no longer needed:

```bash
rm -rf /tmp/biocypher-api-dataset-demo /tmp/biocypher-api-manual-adapter
```

Remove the local default registry database if you want a fresh manual run:

```bash
rm -f registry.sqlite3
```

Only remove `registry.sqlite3` when you intentionally want to discard local
manual verification state.
