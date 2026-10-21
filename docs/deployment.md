# Deployment & Security Architecture

Status: findings from the security review of `src/core/workspace/client_loop.py` and
deployment planning for public multi-user operation alongside the
[biocypher-components-registry](https://github.com/ssciwr/biocypher-components-registry) stack.

## Threat model

`client_loop.py` executes tools that the *model* chooses: four file tools
confined to `FILE_TOOLS_ROOT`, plus `run_command`, which runs arbitrary shell
commands. The attacker is therefore not only a malicious user but **prompt
injection**: MCP tool results, file contents, or any data the model reads can
steer it into emitting hostile commands. Model output must be treated as
untrusted input.

Consequences without isolation:

- `run_command` bypasses all file-tool path confinement (`cwd=FILE_ROOT` is
  cosmetic; the shell can go anywhere the process user can).
- Secrets in the process environment leak into every executed command and are
  one `curl` away from exfiltration.
- On a shared host, one compromised session reaches the registry backend,
  database, and other users' data.

## Hardening already implemented in `client_loop.py`

- **Path confinement** (`_resolve_path`): rejects absolute paths and `..`
  components before any path construction, normalizes and containment-checks
  against the workspace root (Sonar S2083 compliant pattern), and resolves
  symlinks with a final `is_relative_to` check. Applies to `list_dir`,
  `read_file`, `write_file`, `edit_file`.
- **Secret handling** (`read_secret`): secrets come from `<NAME>_FILE`
  (read once, deleted best-effort — intended for tmpfs-mounted per-session
  secrets) or from the env var, which is popped from `os.environ` after
  reading. Either way the secret never sits in the process environment where
  `/proc/*/environ` or child processes could see it. Used for
  `ANTHROPIC_API_KEY` and `BIOCYPHER_MCP_AUTH_HEADER`.
- **Subprocess env allowlist** (`_exec_env`): `run_command` subprocesses get
  only `EXEC_ENV_ALLOWLIST` (`PATH`, `LANG`, `LC_ALL`, `TZ`) plus `HOME` set
  to the workspace, so no backend secret (OAuth/session secrets,
  `DATABASE_URL`, API keys) is inherited.
- **Result caps and timeouts**: tool results truncated at
  `MCP_RESULT_MAX_CHARS`; `run_command` output is read with the same byte
  cap (memory stays bounded) and the command is killed after
  `timeout_seconds` (default 300 s, clamped to `MAX_COMMAND_SECONDS` = 600 s).
- **Sandbox user pool** (`AGENT_SANDBOX_USER_PREFIX` and
  `AGENT_SANDBOX_POOL_SIZE`, set to `sandbox` and 20 in the Docker image,
  build arg `SANDBOX_POOL_SIZE`): the image creates the users
  `sandbox1..N`, and every session leases one of them for its lifetime. The
  session's workspace belongs to its user (mode `0700`), and everything the
  session does runs as that user via sudo: `run_command`, the file tools, the
  file routes and the zip download (`src/core/workspace/workspace_fs.py`).
  The sudoers rule in the `Dockerfile` lets apiuser become pool users only.
  So sessions cannot list, read or write each other's workspaces, nor read
  the cwd or environment of each other's processes; the API user cannot read
  workspaces either. Pool users share only the `sandbox` group, which lets
  them traverse `/app/data` and create their workspace in the workspaces
  root (`1730`: sticky, no read). They cannot reach the registry database,
  the API process's `/proc` entries or the service venv. Each session gets
  its own `.venv` in the workspace for `pip install`, and `TMPDIR` points
  at `.tmp` inside it. On teardown, every process of the user is killed, its
  files in `/tmp`, `/var/tmp` and `/dev/shm` are deleted and the workspace
  is removed before the user returns to the pool. A user is held back from
  the pool if its workspace could not be removed or its session's turn did
  not stop within 10 s. At startup the API removes workspaces (session-id
  directories only) left behind by a crash, and drops pool users that do
  not exist in the image (`AGENT_SANDBOX_POOL_SIZE` above the build arg).
  The pool size is also the global session cap: when every user is leased,
  creating a session returns 429. Leases live in one process, so run the
  API with a **single uvicorn worker**: a lock file in the workspaces root
  makes any further process refuse workspace sessions (429). Needs `sudo` to work in the container, so
  do not set `no-new-privileges`; `init: true` in compose reaps processes
  orphaned by killed commands. Known limit: process command lines are still
  visible to all users through `ps` (hiding them needs `/proc` mounted with
  `hidepid`).
- **Isolation check**: run
  `docker compose -f docker-compose-sqlite.yml run --rm --no-deps backend uv run --no-sync python -m src.core.workspace.isolation_check`
  against a built image after changing the sandbox setup.
- **Workspace download**: capped at `AGENT_MAX_ARCHIVE_BYTES` (default
  200 MiB of zip); larger workspaces get 413.
- **Per-user limits**: at most `AGENT_MAX_SESSIONS_PER_USER` sessions per
  GitHub user; chat messages capped at 100 000 chars; file preview capped at
  1 MB.

What code-level hardening cannot fix: `run_command` is arbitrary code
execution by design. Everything below exists to contain it.

## Deployment architecture

### Disqualified: Nested containers

Running the agent as a "subcontainer" inside the registry backend container
requires Docker-in-Docker (`--privileged` or a mounted Docker socket), which
hands the inner workload a path to root on the host. Strictly worse than the
alternatives.

### Disqualified: Sibling container (single trusted user)

Run the agent as its own service next to the registry's three-tier compose
stack (nginx frontend, FastAPI backend, Postgres):

- Own image, own network (`agent-network`), **not** on the registry's
  `biocypher-network`. The agent never sees the database. Attach the backend
  to both networks only if the agent must reach an MCP endpoint there.
- Dedicated workspace volume mounted at `/workspace`
  (`FILE_TOOLS_ROOT=/workspace`); nothing shared with the registry.
- Hardened container: non-root user, `read_only: true` rootfs with tmpfs
  `/tmp`, `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]`,
  `pids_limit`, `mem_limit`, `cpus`.
- Blast radius of a hostile command: the container and its workspace volume.

### Planned architecture: Per-session containers (public, multi-user)

A single shared agent container cannot separate users: `client_loop` holds
global state (`FILE_ROOT`, `EXEC_BIN`, one conversation history), and any
co-tenant can read any other tenant's files via `run_command`. The unit of
isolation must be **one container per session**:

```
user ──> frontend ──> backend API (auth, session mgmt)
                          │
                          └──> orchestrator (only component with Docker/K8s API access)
                                   └── per-session agent container
                                         - fresh workspace volume, destroyed on teardown
                                         - gVisor/Kata runtime
                                         - resource caps, idle timeout
```

Isolation dimensions:

1. **Filesystem** — fresh volume (or tmpfs) per session, deleted at teardown.
   Sessions never share state; globals in `client_loop` become harmless
   because each process serves exactly one session.
2. **Kernel** — namespaces alone are not enough for public arbitrary code
   execution; a kernel exploit in one session reaches all others. Use gVisor
   (`runtime: runsc`, drop-in for Docker/K8s) or Kata/Firecracker microVMs.
   This is the single most important control for public multi-tenant.
3. **Network** — sessions must not reach each other or the registry DB tier:
   per-session networks or one `internal: true` network with inter-container
   communication disabled. Egress only through an allowlisting proxy
   (Anthropic API + MCP endpoint). This also kills most exfiltration and
   crypto-mining abuse.
4. **Resources / DoS** — per-container `cpus`, `mem_limit`, `pids_limit`,
   disk quota on the workspace volume, session idle timeout, max concurrent
   sessions per user. BYOK does not remove compute abuse.
5. **Orchestration privilege** — the component that spawns containers holds
   Docker-socket-equivalent power. Keep it a minimal internal service with a
   tiny API (create/destroy session), never publicly exposed, never sharing a
   process with request parsing. At scale, Kubernetes does this cleanly:
   pod-per-session, `runtimeClass: gvisor`, `NetworkPolicy`, ephemeral
   volumes, `activeDeadlineSeconds`.

### Bring-your-own-key (BYOK)

Each user supplies their own Anthropic API key through the frontend; there is
no shared key. This removes shared-budget concerns but makes the service a
custodian of user secrets. Key lifecycle:

1. **Frontend**: password-type field, HTTPS only, JS memory or
   `sessionStorage` at most — never `localStorage`, never cookies.
2. **Backend API**: validates the key with one cheap API call, hands it to
   the orchestrator, then forgets it. Never persisted to the database, never
   logged. In-memory session store with TTL at most.
3. **Agent container**: orchestrator mounts the key on a tmpfs (e.g.
   `/run/secrets/anthropic_key`) and sets
   `ANTHROPIC_API_KEY_FILE=/run/secrets/anthropic_key`. `client_loop` reads
   it once, deletes the file, and holds the key only in process memory —
   `/proc/*/environ` stays clean, `run_command` subprocesses never see it.
4. Container teardown destroys the key.

Residual risks and their mitigations:

- A prompt-injected session can at worst leak *its own user's* key, and the
  egress allowlist blocks sending it anywhere except Anthropic.
- If the MCP server exposes **write** tools (e.g. registry submissions), a
  hostile session could publish stolen data into public registry content —
  keep agent-facing MCP read-only, or review/filter writes.
- Cross-session compromise would leak other users' keys; that is what the
  gVisor/Kata layer is for.
- Session-to-user binding still requires real auth on the backend API; the
  key is not an identity.

`client_loop` honors `ANTHROPIC_BASE_URL`, so per-user keys go directly to
Anthropic — no LLM gateway required, and each user sees their own usage in
their own console.

## Build order

1. Per-session containers with fresh volumes, hardened options, resource caps.
2. gVisor (or Kata/Firecracker) runtime for the agent containers.
3. BYOK key flow via `ANTHROPIC_API_KEY_FILE` on tmpfs (client support is
   already implemented).
4. Egress allowlisting proxy on the agent network.
5. Session lifecycle: idle timeout, teardown, per-user session limits.

This order front-loads the controls that prevent cross-user compromise; the
later items limit cost abuse and exfiltration.

## Open items

- `client_loop` is a stdin/stdout CLI; public deployment needs an I/O layer
  (attach to container stdio, or convert the loop to a websocket/SSE handler
  per the FastAPI plan in [PLAN.md](PLAN.md)). Tool logic carries over
  unchanged.
- `select_exec_env` prompts interactively for a Python environment; in a
  container this should be pinned via configuration instead.
- Decide the concrete orchestrator (compose + small spawner service vs.
  Kubernetes) based on expected scale.
