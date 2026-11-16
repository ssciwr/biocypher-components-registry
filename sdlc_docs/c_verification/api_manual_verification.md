# API Manual Verification With HTTPie

This checklist verifies the current FastAPI contract manually with HTTPie.

## Consult Swagger First

Before using the command-line examples below, inspect the API contract generated
by the exact backend revision being verified:

```text
Swagger UI:   http://localhost:8000/docs
ReDoc:        http://localhost:8000/redoc
OpenAPI JSON: http://localhost:8000/openapi.json
```

Expand an operation in Swagger to inspect its parameters, request body,
responses, status codes, and component schemas. **Try it out** sends the request
to the running backend. Mutating operations use its configured database, so use
a disposable development database.

Swagger does not bypass authorization. GitHub-protected operations require the
normal authenticated browser session cookie. OAuth redirect routes marked with
`include_in_schema=False` are intentionally absent from Swagger. Optional
agentic-workspace routes appear only when their router is enabled.

If an HTTPie example disagrees with the generated contract, treat the live
OpenAPI document as authoritative and update this guide.

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
docker compose -f docker-compose-sqlite.yml up --build backend
```

When using SQLite Compose, the database is `/app/data/registry.sqlite3` in the
`biocypher-sqlite-data` named volume. Host-local demo paths are only visible to a
host API process unless explicitly mounted into the container.

For registration/update requests, sign in through the existing browser GitHub
flow and supply its local session cookie to HTTPie. In the examples,
`SESSION_COOKIE` means the full cookie pair `bcr_session=<local-session-token>`.
Use the same hostname as the signed-in browser. Public reads and standalone
metadata utilities do not require this cookie.

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

Generate dataset metadata from one local CSV file using the standalone multipart
endpoint. Replace `./people.csv` with an existing UTF-8 CSV file:

```bash
http --form POST :8000/api/v1/metadata/datasets/generate \
  file@./people.csv \
  generator=native \
  validate=true \
  name="People Demo Dataset" \
  description="Small CSV dataset used to verify generation." \
  url=https://example.org/people-demo \
  license=https://opensource.org/licenses/MIT \
  citation=https://example.org/people-demo \
  dataset_version=1.0.0 \
  date_published=2026-04-17 \
  creators_json='[{"name":"Dataset Creator","creator_type":"Person"}]'
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

With a signed-in session, submit the local demo repository to the host API:

```bash
http POST :8000/api/v1/registrations \
  Cookie:"$SESSION_COOKIE" \
  repository_location=/tmp/biocypher-api-manual-adapter
```

Expected result:

- HTTP `201`, terminal `attempt_status: SUCCEEDED`
- `registration_id`, metadata-derived `adapter_id` and name
- `published_version: 1.0.0`
- one accepted source, canonical entry and `VALID_CREATED` event
- no separate process request

Save the returned identifiers. Repeating the same accepted repository returns
`409`; updating it uses the owned adapter action in section 9. Without sign-in,
publication returns `401`.

For a separate first-registration run, choose the streaming alternative before
the repository is accepted:

```bash
http --stream POST :8000/api/v1/registrations/stream \
  Cookie:"$SESSION_COOKIE" \
  repository_location=/tmp/biocypher-api-manual-adapter
```

Expect `snapshot`, `check` and one terminal `result` or `error`, with heartbeat
comments. Only the terminal result confirms persistence. A disconnected client
must inspect the catalog before another submission, without automatic retries.

Inspect accepted state and history:

```bash
http GET :8000/api/v1/registrations/<registration_id>
http GET :8000/api/v1/registrations/<registration_id>/events
http GET :8000/api/v1/registrations
http GET :8000/api/v1/schemas/v1
```

Read responses separate `published_version` and `latest_attempt`, with no
lifecycle `status`. The schema response has `application/schema+json`; an unknown
version returns `404`.

For a rejection test, use an unregistered copy with invalid JSON or missing
required metadata. Expect HTTP `200`, `attempt_status: FAILED`, no registration
identifier and available validation errors/positions/checks. Confirm no source,
entry or event was saved. Correcting the file allows retry with the same version.
Do not confuse a rejected new source with an update of an already accepted one.

## 7. Registry Operations

Run a trusted batch refresh against the same configured database through the CLI:

```bash
uv run cli.py refresh-registry
uv run cli.py show-latest-refresh
```

The API has no batch-trigger route. Read its latest completed summary:

```bash
http GET :8000/api/v1/registry/refreshes/latest
```

Expect run ID/timestamps and `active_sources`, `processed`, `valid_created`,
`unchanged`, `invalid`, `duplicate`, `rejected_same_version_changed`,
`fetch_failed` and `internal_failed`. With no completed refresh, expect `404`.

List published sources and filter the latest persisted event:

```bash
http GET :8000/api/v1/registry/registrations
http GET :8000/api/v1/registry/registrations latest_event==INVALID_SCHEMA
http GET :8000/api/v1/registry/registrations latest_event==missing
```

The last request returns `422`. The former lifecycle `status` filter is removed.
Rows retain the accepted version even when their latest update failed.

Read canonical entry summaries without full metadata:

```bash
http GET :8000/api/v1/registry/entries
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

Read the latest accepted metadata for one adapter:

```bash
http GET :8000/api/v1/adapters/<adapter_id>/metadata
```

For the demo document, likely values are:

```text
adapter_id = manual-example-adapter
version = 1.0.0
```

## 9. Manual Updates and Retries

Update the demo metadata version to a different unused label while preserving
its adapter identity, then call the owner-authorized action:

```bash
http POST :8000/api/v1/adapters/<adapter_id>/update Cookie:"$SESSION_COOKIE"
```

Expected result:

- unchanged metadata: `SUCCEEDED`, existing published version, no replacement
- accepted changed metadata: `SUCCEEDED`, new published version, `update_applied: true`
- invalid candidate: `FAILED`, accepted version/metadata retained, failure event
- changed content reusing the current version: `FAILED`, `VERSION_NOT_BUMPED`
- a different account: `403`; an unknown adapter: `404`

Labels need not increase semantically; they must be different and unused for a
changed candidate. Correct an invalid update and repeat Update to retry. Correct
a rejected first registration and submit its repository again; no failed-source
revalidation endpoint exists.

The CLI supports the same owner-authorized operation with separate device
authentication:

```bash
uv run cli.py update <adapter-id>
uv run cli.py update <adapter-id> --force-validation
```

Confirm failed update attempts do not change the public metadata endpoint and
remain visible in source event history.

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
