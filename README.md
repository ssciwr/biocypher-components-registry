# BioCypher Components Registry

A production-grade registry system for BioCypher adapters with automated validation, metadata generation, and batch processing capabilities.

## Features

- **Automated Discovery**: Find and validate `croissant.jsonld` metadata files
- **Multi-Layer Validation**: MLCroissant + schema validation
- **Dual Database Support**: SQLite (development) and PostgreSQL (production)
- **Batch Processing**: Non-blocking registry refresh with isolated error handling
- **Multiple Interfaces**: CLI, Web UI, and REST API
- **Event Sourcing**: Complete audit trail of all registration attempts
- **Duplicate Prevention**: Enforced uniqueness by adapter_id + version
- **On-Demand Revalidation**: Fix and reprocess failed registrations

## Quick Start

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- (Optional) Docker and Docker Compose for containerized deployment
- pnpm/node for the frontend local development

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/ssciwr/biocypher-components-registry.git
   cd biocypher-components-registry
   ```

#### Installation - backend:
2. **Install dependencies:**
   ```bash
   uv sync
   ```

3. **Activate the virtual environment:**
   ```bash
   source .venv/bin/activate
   ```
#### Installation - frontend:
2. **Install dependencies:**
```bash
pnpm run install
```


## Usage

For the frontend, you can launch the webserver this way from `/frontend`: `pnpm run dev` which will open to http://localhost:5173

### CLI Interface

The CLI provides complete control over the registry. Use `uv run cli.py` or activate the virtual environment first.

#### Get Help

```bash
# Show all available commands
uv run cli.py --help

# Show help for a specific command
uv run cli.py submit-registration --help
```

#### Registration Workflow

**1. Submit a registration:**

```bash
# Local repository
uv run cli.py submit-registration --name "My Adapter" /path/to/adapter-repo

# Remote GitHub repository
uv run cli.py submit-registration --name "My Adapter" https://github.com/user/adapter-repo
```

**2. Process the registration:**

```bash
# Finish a single registration
uv run cli.py finish-registration <registration-id>
```

**3. List all registrations:**

```bash
uv run cli.py list
```

**4. View registration details:**

```bash
uv run cli.py show-events <registration-id>
```

#### Batch Operations

**Refresh all active registrations:**

```bash
# Process all active sources in one batch
uv run cli.py refresh-registry

# View latest batch refresh summary
uv run cli.py show-latest-refresh
```

**Revalidate a failed registration:**

```bash
uv run cli.py revalidate-registration <registration-id>
```

#### Registry Queries

**List canonical valid entries:**

```bash
uv run cli.py list-registry-entries
```

**Discover and validate adapter metadata:**

```bash
# Discover from local path
uv run cli.py discover /path/to/adapter-repo

# Discover from GitHub URL
uv run cli.py discover https://github.com/user/adapter-repo
```

#### Validation

**Validate metadata files:**

```bash
# Auto-detect type (adapter or dataset)
uv run cli.py validate /path/to/croissant.jsonld

# Validate as adapter
uv run cli.py validate-adapter /path/to/croissant.jsonld

# Validate as dataset
uv run cli.py validate-dataset /path/to/croissant.jsonld
```

### Web Interface

Launch the legacy web interface for interactive registration management:

```bash
uv run cli.py web
```

**Access the web UI:**
- URL: http://localhost:8000
- Default host: `127.0.0.1`
- Default port: `8000`

**Custom host/port:**

```bash
# Bind to all interfaces
uv run cli.py web --host 0.0.0.0 --port 8080

# Specify output directory for generated files
uv run cli.py web --output-dir ./output
```

**Features:**
- Submit new registrations via web form
- View registration status and history
- Revalidate failed registrations
- Browse canonical registry entries
- View batch refresh summaries

### REST API

The FastAPI REST API provides programmatic access to the registry.

**Start the API server:**

```bash
uv run uvicorn src.api.app:app --host 0.0.0.0 --port 8000
```

**API Documentation:**
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

**Example API calls:**

```bash
# Health check
curl http://localhost:8000/api/v1/health

# List all registrations
curl http://localhost:8000/api/v1/registrations

# Submit a registration
curl -X POST http://localhost:8000/api/v1/registrations \
  -H "Content-Type: application/json" \
  -d '{
    "adapter_name": "my-adapter",
    "repository_location": "/path/to/repo",
    "repository_kind": "local"
  }'

# List canonical registry entries
curl http://localhost:8000/api/v1/registry/registrations

# Trigger batch refresh
curl -X POST http://localhost:8000/api/v1/registry/refreshes
```

## Database Configuration

The registry supports both SQLite and PostgreSQL.

### SQLite (Default - Development)

SQLite is used by default for local development:

```bash
# Uses registry.sqlite3 in current directory
uv run cli.py list

# Custom database path
export BIOCYPHER_REGISTRY_DB_PATH=/path/to/custom.db
uv run cli.py list
```

### PostgreSQL (Production)

For production deployments, use PostgreSQL:

```bash
# Set PostgreSQL connection string
export DATABASE_URL=postgresql://user:password@localhost:5432/biocypher_registry

# All CLI commands now use PostgreSQL
uv run cli.py list
uv run cli.py web
```

**Database selection logic:**
- If `DATABASE_URL` is set → PostgreSQL
- Otherwise → SQLite (default)

## Docker Deployment

### SQLite (Development)

```bash
# Start all tiers with SQLite
docker compose -f docker-compose-sqlite.yml up

# Access the services
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000/docs
```

### PostgreSQL (Production)

```bash
# Start all tiers with PostgreSQL
docker compose -f docker-compose-postgresql.yml up

# Access the services
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000/docs
# Database: localhost:5432
```

**Services:**
- **frontend**: nginx serving placeholder UI (port 3000)
- **backend**: FastAPI application (port 8000)
- **database**: PostgreSQL 16-alpine (port 5432, PostgreSQL only)

For detailed Docker instructions, see [DOCKER.md](DOCKER.md).

## Common CLI Workflows

### Register and Process a New Adapter

```bash
# 1. Submit registration
uv run cli.py submit-registration --name "OmniPath Adapter" \
  https://github.com/user/omnipath-adapter

# 2. Finish registration (validates and stores if valid)
uv run cli.py finish-registration <registration-id>

# 3. Verify it's in the registry
uv run cli.py list-registry-entries
```

### Fix a Failed Registration

```bash
# 1. View the error details
uv run cli.py show-events <registration-id>

# 2. Fix the croissant.jsonld file in your repository

# 3. Revalidate
uv run cli.py revalidate-registration <registration-id>
```

### Batch Process All Active Sources

```bash
# Process all active registrations in one run
uv run cli.py refresh-registry

# View summary of what was processed
uv run cli.py show-latest-refresh
```

### Just Validate a File (No Registration)

```bash
# Quick validation without submitting to registry
uv run cli.py validate /path/to/croissant.jsonld
```

## Project Structure

```text
biocypher-components-registry/
├── cli.py                          # CLI entry point
├── src/
│   ├── api/                        # FastAPI REST API layer
│   │   ├── app.py                  # API application
│   │   ├── routers/                # API endpoints
│   │   └── schemas/                # Request/response models
│   ├── core/                       # Business logic
│   │   ├── adapter/                # Adapter discovery & generation
│   │   ├── dataset/                # Dataset generation
│   │   ├── registration/           # Registration services
│   │   ├── schema/                 # Validation schemas
│   │   ├── validation/             # Validation logic
│   │   └── web/                    # Legacy web server
│   └── persistence/                # Database adapters
│       ├── tables.py               # SQLAlchemy table definitions
│       ├── registration_sqlite_store.py
│       └── registration_postgres_store.py
├── tests/                          # Unit and BDD tests
├── sdlc_docs/                      # Architecture and design docs
├── docker-compose-sqlite.yml       # SQLite deployment
├── docker-compose-postgresql.yml   # PostgreSQL deployment
└── DOCKER.md                       # Docker documentation
```

## Development

### Run Tests

```bash
# All tests
uv run pytest

# Specific test file
uv run pytest tests/unit/test_cli_submit.py

# With coverage
uv run pytest --cov=src
```

From the frontend:
`pnpm run ui-tests`
this will require having previously ran the *project-specific* cypress installer: `pnpm cypress install`

### Code Quality

```bash
# Format code
uv run ruff format

# Lint
uv run ruff check

# Type check
uv run mypy src/
```

From /frotnend:
`pnpm run lint`

## Documentation

- **[DOCKER.md](DOCKER.md)** - Complete Docker and Docker Compose guide
- **[sdlc_docs/](sdlc_docs/)** - Architecture, design, and ADRs
- **[API Documentation](http://localhost:8000/docs)** - Interactive API docs (when server is running)

## Architecture

The registry follows a three-tier architecture:

1. **Frontend Tier**: nginx (placeholder, React planned)
2. **Backend Tier**: FastAPI API + Core services + Persistence adapters
3. **Database Tier**: SQLite (dev) or PostgreSQL (prod)

Key architectural patterns:
- **Ports-and-adapters** for database independence
- **Event sourcing** for complete audit trails
- **Service layer** for business logic isolation
- **REST API** for external integration

See [sdlc_docs/b_design/architecture.md](sdlc_docs/b_design/architecture.md) for details.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | None (uses SQLite) |
| `BIOCYPHER_REGISTRY_DB_PATH` | SQLite database file path | `registry.sqlite3` |

## Troubleshooting

### CLI Command Not Found

Ensure you've activated the virtual environment or use `uv run`:

```bash
source .venv/bin/activate
python cli.py --help
```

### Database Connection Error

Check your database configuration:

```bash
# SQLite: verify file exists and is readable
ls -la registry.sqlite3

# PostgreSQL: verify connection string
echo $DATABASE_URL
```

### Web Interface Port Already in Use

Change the port:

```bash
uv run cli.py web --port 8080
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## License

See [LICENSE](LICENSE) for details.
