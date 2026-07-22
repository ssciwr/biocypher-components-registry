# BioCypher Components Registry

[![codecov](https://codecov.io/gh/ssciwr/biocypher-components-registry/graph/badge.svg?token=V6MMJ2L1O6)](https://codecov.io/gh/ssciwr/biocypher-components-registry)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/ssciwr/biocypher-components-registry/main.svg)](https://results.pre-commit.ci/latest/github/ssciwr/biocypher-components-registry/main)

Registry system for BioCypher adapters with metadata validation, registration workflows, persistence, and API/CLI access.

The project currently contains:

- a Python backend with CLI commands and a FastAPI REST API
- SQLite support for local development and PostgreSQL support for deployment-oriented setups
- a React/Vite frontend scaffold under `frontend/` (static landing page, not yet wired to the API)
- unit and BDD tests for core, API, persistence, and CLI behavior

## Requirements

- Python 3.12+ (the Docker image uses Python 3.13)
- [uv](https://docs.astral.sh/uv/) for Python dependency management
- Node.js 24+ and pnpm for frontend development
- Docker and Docker Compose, optional

## Backend Setup

Install Python dependencies:

```bash
uv sync
```

Install development dependencies, including pytest:

```bash
uv sync --group dev
```

Other optional dependency groups defined in `pyproject.toml`:

- `api-client`: installs `httpie` for ad hoc API calls (`uv sync --group api-client`)
- `performance`: installs `locust` for load testing against `locustfile.py` (`uv sync --group performance`)

Run backend tests:

```bash
uv run pytest
```

Run a specific test file:

```bash
uv run pytest tests/unit/test_cli_submit.py
```

## CLI Usage

Show available commands:

```bash
uv run cli.py --help
```

Submit an adapter registration (persisted to the configured database):

```bash
uv run cli.py submit-registration --name "My Adapter" /path/to/adapter-repo
uv run cli.py submit-registration --name "My Adapter" https://github.com/user/adapter-repo
```

Process a submitted registration:

```bash
uv run cli.py finish-registration <registration-id>
```

Inspect registrations and events:

```bash
uv run cli.py list-registrations
uv run cli.py show-registration-events <registration-id>
uv run cli.py list-registry-entries
```

Refresh or revalidate registrations:

```bash
uv run cli.py refresh-registry
uv run cli.py show-latest-refresh
uv run cli.py revalidate-registration <registration-id>
```

Discover a single adapter `croissant.jsonld` from a local path or GitHub URL and validate it:

```bash
uv run cli.py discover /path/to/adapter-repo
```

Validate metadata directly:

```bash
uv run cli.py validate /path/to/croissant.jsonld
uv run cli.py validate-adapter /path/to/croissant.jsonld
uv run cli.py validate-dataset /path/to/croissant.jsonld
```

Build a registration request without persisting it:

```bash
uv run cli.py submit --name "My Adapter" /path/to/adapter-repo
```

### Metadata Generation Commands

The `adapter` and `dataset` command groups generate Croissant metadata files. Each group supports `direct` (flags), `guided` (interactive prompts), and `config` (YAML file) modes:

```bash
uv run cli.py dataset guided
uv run cli.py dataset config --config dataset.yaml
uv run cli.py dataset direct --input /path/to/data --name "My Dataset" --description "..." --url "https://..." --license "CC-BY-4.0" --citation "..."

uv run cli.py adapter guided
uv run cli.py adapter config --config adapter.yaml
uv run cli.py adapter direct --name "My Adapter" --description "..." --version "1.0.0" --license "MIT" --code-repository "https://..." --keywords "graph,biology" --creator "Name, Affiliation, Identifier" --dataset-path /path/to/dataset-croissant.jsonld
```

Run `uv run cli.py adapter --help` or `uv run cli.py dataset --help` for the full flag list of each mode.

## Agentic workspace
The agentic workspace can be run through the API or directly through the command-line using

    uv run python src/core/workspace/client_loop.py

Be aware that currently you need a Claude API key, provided via environment variables:

    export ANTHROPIC_API_KEY="<your key>"
    # or
    export ANTHROPIC_API_KEY_FILE="secrets/anthropic_api_key"
For more information on the agentic workspace, consult its [dedicated documentation](docs/agentic_workspace.md).

## REST API

Start the FastAPI application:

```bash
uv run uvicorn src.api.app:app --host 0.0.0.0 --port 8000
```

Useful local URLs:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

All routes below are served under the `/api/v1` prefix.

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | API liveness check |
| GET | `/adapters` | List public adapters derived from canonical registry entries |
| GET | `/adapters/{adapter_id}` | Get one public adapter with its registered canonical versions |
| GET | `/adapters/{adapter_id}/versions/{version}/metadata` | Get full Croissant metadata for one adapter version |
| POST | `/registrations` | Submit an adapter registration |
| GET | `/registrations` | List active registrations |
| GET | `/registrations/{registration_id}` | Get one registration detail |
| GET | `/registrations/{registration_id}/events` | List event history for one registration |
| POST | `/registrations/{registration_id}/process` | Discover, validate, and persist a submitted registration |
| POST | `/registrations/{registration_id}/revalidate` | Reprocess one invalid or fetch-failed registration |
| GET | `/registry/registrations` | List registry registration rows with public status and latest event |
| GET | `/registry/entries` | List canonical valid registry entries |
| GET | `/registry/entries/{entry_id}` | Get one canonical valid registry entry |
| GET | `/registry/refreshes/latest` | Get the latest persisted batch refresh summary |
| POST | `/registry/refreshes` | Process all active registrations once |
| POST | `/metadata/validate` | Validate inline adapter or dataset metadata without persisting it |
| POST | `/metadata/datasets/generate` | Generate dataset Croissant metadata from server-side files |
| POST | `/metadata/adapters/generate` | Generate adapter Croissant metadata from existing/generated datasets |

Example requests:

```bash
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/registrations

curl -X POST http://localhost:8000/api/v1/registrations \
  -H "Content-Type: application/json" \
  -d '{
    "adapter_name": "my-adapter",
    "repository_location": "/path/to/repo",
    "contact_email": "maintainer@example.org"
  }'

curl http://localhost:8000/api/v1/registry/registrations
curl -X POST http://localhost:8000/api/v1/registry/refreshes
curl http://localhost:8000/api/v1/adapters
```

## Frontend Setup

The React/Vite frontend lives in `frontend/`.

Install dependencies:

```bash
cd frontend
pnpm install
```

Run the development server:

```bash
pnpm run dev
```

Run frontend checks:

```bash
pnpm run lint
pnpm run build
```

The frontend is expected to consume the backend through the `/api/v1` API. See `sdlc_docs/b_design/frontend/frontend_api_contract.md` for the current API contract.

## Database Configuration

The backend uses SQLite by default.

```bash
uv run cli.py list-registrations
```

Set a custom SQLite database path:

```bash
export BIOCYPHER_REGISTRY_DB_PATH=/path/to/custom.db
uv run cli.py list-registrations
```

Use PostgreSQL by setting `DATABASE_URL`:

```bash
export DATABASE_URL=postgresql://user:password@localhost:5432/biocypher_registry
uv run cli.py list-registrations
```

Database selection:

- `DATABASE_URL` set: PostgreSQL
- otherwise: SQLite

## Docker Compose

Docker files are available for local backend/database experiments:

```bash
docker compose -f docker-compose-sqlite.yml up
docker compose -f docker-compose-postgresql.yml up
```

The compose files expose the backend API on http://localhost:8000. The PostgreSQL compose file also exposes the database on port 5432 and requires `POSTGRES_PASSWORD` to be set (via a `.env` file with `KEY=VALUE` lines or exported shell variables); it fails fast if that variable is missing. `POSTGRES_DB` and `POSTGRES_USER` are optional and default to `biocypher_registry` and `biocypher`. The frontend service in both compose files points at a `./frontend-placeholder` directory and only serves a static Nginx placeholder; it is not wired to the real `frontend/` app. For frontend development, use the Vite workflow in `frontend/` instead.

## Project Structure

```text
biocypher-components-registry/
├── cli.py                         # CLI entry point (registration, validation, metadata generation)
├── locustfile.py                  # Optional Locust load-testing scenario
├── frontend/                      # React/Vite frontend scaffold
├── src/
│   ├── api/                       # FastAPI REST API layer
│   │   ├── app.py                 # Application factory
│   │   ├── routers/                # health, adapters, registrations, registry, metadata
│   │   └── schemas/                 # Request/response models
│   ├── core/                      # Business logic: adapter, dataset, registration, schema, validation
│   └── persistence/               # SQLite/PostgreSQL adapters and SQLAlchemy tables
├── data/in/                       # Sample Croissant metadata and datasets used by tests/CI
├── tests/                         # Python unit and BDD tests
├── sdlc_docs/                     # Requirements, design docs, ADRs, verification notes
├── docker-compose-sqlite.yml
├── docker-compose-postgresql.yml
├── pyproject.toml
└── uv.lock
```

## CI

GitHub Actions workflows are stored in `.github/workflows/`.

- `backend.yml`: installs Python dependencies with uv and runs `uv run pytest` with coverage, uploaded to Codecov. Triggered on pull requests touching `src/`, `tests/`, `cli.py`, or dependency files.
- `frontend.yml`: installs frontend dependencies with pnpm, then runs `pnpm run lint` and `pnpm run build`. Triggered on pull requests touching `frontend/`.
- `validate_schema.yml`: validates the sample `data/in/adapter_collectri/collectri.json` Croissant file against the schema using the `ssciwr/validate-croissant-schema` action.

## Documentation

- `sdlc_docs/b_design/architecture.md`: overall architecture
- `sdlc_docs/b_design/backend/`: backend and persistence design
- `sdlc_docs/b_design/frontend/`: frontend architecture and API contract
- `sdlc_docs/c_verification/`: manual verification notes and compatibility checks

## Environment Variables

| Variable | Description | Default |
| --- | --- | --- |
| `DATABASE_URL` | PostgreSQL connection string | unset; SQLite is used |
| `BIOCYPHER_REGISTRY_DB_PATH` | SQLite database file path | `registry.sqlite3` |
| `POSTGRES_DB` | PostgreSQL database name (Docker Compose only) | `biocypher_registry` |
| `POSTGRES_USER` | PostgreSQL user (Docker Compose only) | `biocypher` |
| `POSTGRES_PASSWORD` | PostgreSQL password (Docker Compose only) | required; no default |

## Troubleshooting

If a CLI command is not found, use `uv run` from the repository root:

```bash
uv run cli.py --help
```

If the API port is already in use, choose another port:

```bash
uv run uvicorn src.api.app:app --host 0.0.0.0 --port 8080
```

If `docker compose -f docker-compose-postgresql.yml up` exits immediately with a `POSTGRES_PASSWORD is required` error, set `POSTGRES_PASSWORD` (and optionally `POSTGRES_DB`/`POSTGRES_USER`) as shell environment variables or in a `.env` file using `KEY=VALUE` syntax (not `KEY:VALUE`) before starting the stack.

If dependency installation fails, confirm that network access is available for Python packages, Git dependencies, and npm packages used by the frontend.

## Contributing

See `CONTRIBUTING.md` for contribution guidelines.

## License

See `LICENSE` for details.
