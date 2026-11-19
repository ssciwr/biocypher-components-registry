# Component classification and STITCH metadata

Adapter generation always emits `componentType: "adapter"`. There is no component
type selector in the adapter creation UI. Granularity is optional: `Primary`
means an adapter for one atomic resource; `Secondary` means an adapter for a
composite, often pre-harmonized resource. These follow the
[BioCypher definitions](https://biocypher.org/BioCypher/learn/explanation/adapters/).
The number of input files does not determine granularity.

The adapter JSON Schema also accepts `componentType: "pipeline"`. If a pipeline
specifies granularity, it must be the string `"none"`, meaning not applicable.
An adapter cannot specify `"none"`. Omission means unspecified, not Primary.
Existing documents without either property remain valid. Pipeline composition
and pipeline generation are not introduced by this change: `hasPart` still
contains dataset descriptions.

The short JSON-LD properties have these vocabulary identifiers, defined by this
registry profile:

| Property | Vocabulary identifier |
| --- | --- |
| `componentType` | `https://biocypher.org/registry/terms/componentType` |
| `granularity` | `https://biocypher.org/registry/terms/granularity` |

These are BioCypher profile terms, not Croissant terms or retrieval endpoints.
The generated adapter context includes their mappings. A manually authored
document should include the same mappings in its context.

Generation supports `--granularity Primary` / `--granularity Secondary`, a
`granularity` entry under `adapter` in YAML configuration, and a guided prompt.
The metadata-generation API accepts an optional `granularity`. Its component
type is constrained to adapter; it rejects pipeline creation requests.

Dataset landing pages remain `hasPart[].url`; downloadable resources remain
`distribution[].contentUrl`. Catalog resource types and formats display the
actual Croissant `@type` and `encodingFormat` values. API access is not inferred
from MIME types or added as a replacement for `FileObject` or `FileSet`.

## Start PostgreSQL and the API

From the components-registry root, put your PostgreSQL password in `.env`:

```dotenv
POSTGRES_PASSWORD=replace-with-your-local-password
```

Start the backend and database with the updated code:

```bash
docker compose -f docker-compose-postgresql.yml up -d --build database backend
```

Open `http://localhost:8000/docs` to verify that the API is available.
Metadata generation does not require GitHub sign-in. Registration does.

This Compose file's `frontend` service is an Nginx placeholder. Run the real
frontend separately, from a second terminal:

```bash
cd frontend
pnpm install --frozen-lockfile
VITE_API_BASE_URL=http://localhost:8000 pnpm run dev --host 127.0.0.1 --port 5173
```

Open `http://localhost:5173/create/adapter-metadata?start=1`.

## Generate STITCH adapter metadata in the frontend

Fill in **Adapter details**:

| Field | Example |
| --- | --- |
| Name | STITCH BioCypher Adapter |
| Adapter ID | stitch-adapter |
| Adapter granularity | Primary, matching the existing BioCypher board classification |
| Version | 0.1.0, the version declared by the MetaLinks project |
| Repository URL | https://github.com/biocypher/metalinks |
| Adapter license | The verified software license; the repository LICENSE is GPL-3.0 |
| Keywords | STITCH, metabolites, proteins, BioCypher |
| Description | Describe the STITCH adapter and its identifier-mapping dependencies |
| Creators | The verified software authors, separate from dataset creators |

The help icon beside granularity explains Primary and Secondary. Leave it
unspecified if classification has not been established. The software license is
separate from licenses for the STITCH data.

### Reuse the reviewed dataset descriptions

The frontend imports dataset Croissant documents, not an adapter Python file or
the entire adapter wrapper. If using the existing STITCH adapter metadata,
extract its two embedded datasets first. Run this locally, adjusting the input
path to your checkout:

```bash
python3 - <<'PY'
import json
from pathlib import Path

source = Path('../metalinks/metalinks/metadata/stitch_croissant.jsonld')
document = json.loads(source.read_text())
output = Path('/tmp/stitch-datasets')
output.mkdir(exist_ok=True)
for index, dataset in enumerate(document['hasPart'], start=1):
    standalone = {'@context': document['@context'], **dataset}
    path = output / f'stitch-dataset-{index}.jsonld'
    path.write_text(json.dumps(standalone, indent=2) + '\n')
    print(path)
PY
```

In **Basic dataset info**, choose **Upload existing dataset Croissant file**.
Add each extracted file as a separate dataset, then review both in the dataset
details step. The original document's unknown licenses and provenance caveats
are preserved; this feature does not resolve the STITCH/Zenodo licensing
discrepancy or supply missing mapping distributions.

### Alternatively, inspect the original TSV data

Select **I need to generate a Croissant file for the dataset too** and upload
each local Zenodo TSV separately:

- [9606.actions.v5.0.tsv](https://zenodo.org/records/10200150/files/9606.actions.v5.0.tsv?download=1)
- [9606.protein_chemical.links.detailed.v5.0.tsv](https://zenodo.org/records/10200150/files/9606.protein_chemical.links.detailed.v5.0.tsv?download=1)

These are the files consumed by MetaLinks. The frontend does not download data
from the URL you enter: select the actual local files. Large files are sampled
for inspection and hashed as originals by the browser. Enter the STITCH landing
page separately from each Zenodo download URL. Version `5.0` describes STITCH;
identify the archive publication date explicitly if using `2023-11-23`.

Review inferred field types, particularly the detailed table's `experimental`,
`prediction`, `database`, `textmining`, and `combined_score`: these are integer
scores. Baker's `cr:Int64` is an integer type and is preserved by the editor;
Native's `sc:Integer` is also supported. Unfamiliar types and datatype arrays
remain intact unless explicitly replaced in the datatype selector.
Do not infer their scientific types from a sample containing only zero
and one. Resolve or explicitly retain unknown dataset licenses according to
your team's review; do not copy the adapter software license onto the data.

## Review and download

Generate the adapter Croissant, inspect validation results, and download the
finished file. The result contains `componentType: "adapter"` and your selected
granularity. Save it as `stitch_croissant.jsonld` in the intended MetaLinks
metadata directory.

Validate it with the registry CLI, from the registry root:

```bash
uv run cli.py validate-adapter /path/to/metalinks/metalinks/metadata/stitch_croissant.jsonld
```

Generation does not execute the STITCH adapter, verify that all runtime inputs
are documented, or register the result. Nested component files are not yet
automatically discovered by the registry's root-level repository registration.
