# BioCypher Components Registry

Registry system for BioCypher adapters with metadata validation, registration workflows, persistence, and API/CLI access.

The project currently contains:

- a Python backend with CLI commands, a legacy web UI, and a FastAPI REST API
- SQLite support for local development and PostgreSQL support for deployment-oriented setups
- a React/Vite frontend scaffold under `frontend/`
- unit and BDD tests for core, API, persistence, and CLI behavior

## Requirements

- Python 3.13+
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

Submit an adapter registration:

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
uv run cli.py list
uv run cli.py show-events <registration-id>
uv run cli.py list-registry-entries
```

Refresh or revalidate registrations:

```bash
uv run cli.py refresh-registry
uv run cli.py show-latest-refresh
uv run cli.py revalidate-registration <registration-id>
```

Validate metadata directly:

```bash
uv run cli.py validate /path/to/croissant.jsonld
uv run cli.py validate-adapter /path/to/croissant.jsonld
uv run cli.py validate-dataset /path/to/croissant.jsonld
```

## REST API

Start the FastAPI application:

```bash
uv run uvicorn src.api.app:app --host 0.0.0.0 --port 8000
```

Useful local URLs:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

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
```

## Legacy Web UI

The Python backend still includes a server-rendered web interface for registration management:

```bash
uv run cli.py web
```

Default URL: http://localhost:8000

Custom host or port:

```bash
uv run cli.py web --host 0.0.0.0 --port 8080
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
uv run cli.py list
```

Set a custom SQLite database path:

```bash
export BIOCYPHER_REGISTRY_DB_PATH=/path/to/custom.db
uv run cli.py list
```

Use PostgreSQL by setting `DATABASE_URL`:

```bash
export DATABASE_URL=postgresql://user:password@localhost:5432/biocypher_registry
uv run cli.py list
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

The compose files expose the backend API on http://localhost:8000. The frontend container wiring is still legacy and should be reviewed before using Docker Compose as the primary frontend development path. For frontend development, use the Vite workflow in `frontend/`.

## Project Structure

```text
biocypher-components-registry/
├── cli.py                         # CLI entry point
├── frontend/                      # React/Vite frontend scaffold
├── src/
│   ├── api/                       # FastAPI REST API layer
│   ├── core/                      # Business logic and legacy web server
│   └── persistence/               # SQLite/PostgreSQL adapters
├── tests/                         # Python unit and BDD tests
├── sdlc_docs/                     # Requirements, design docs, ADRs, verification notes
├── docker-compose-sqlite.yml
├── docker-compose-postgresql.yml
├── pyproject.toml
└── uv.lock
```

## CI

GitHub Actions workflows are stored in `.github/workflows/`.

- Backend workflow: installs Python dependencies with uv and runs `uv run pytest`.
- Frontend workflow: installs frontend dependencies with pnpm, then runs lint and build.

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

## Troubleshooting

If a CLI command is not found, use `uv run` from the repository root:

```bash
uv run cli.py --help
```

If the web UI port is already in use, choose another port:

```bash
uv run cli.py web --port 8080
```

If dependency installation fails, confirm that network access is available for Python packages, Git dependencies, and npm packages used by the frontend.

## Contributing

See `CONTRIBUTING.md` for contribution guidelines.

## License

See `LICENSE` for details.
