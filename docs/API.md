# Agentic Workspace API

HTTP/SSE API of the workspace backend (`src/api/routers/workspace.py` +
`src/core/workspace/service.py`, request/response models in
`src/api/schemas/workspace.py`). It serves the three-pane workspace UI —
chat, directory tree, file preview — as part of the main
biocypher-components-registry FastAPI app, alongside the registration and
registry routes under `/api/v1`.

All workspace routes live under a configurable prefix, default:

```
/agent/api/v1
```

kept distinct from the registry's `/api/v1` prefix (`settings.api_v1_prefix`)
so the workspace routes can sit behind the registry's nginx unchanged.
Override with the `AGENT_API_PREFIX` env var.

Run the server (from the repo root):

```bash
uv sync
uv run uvicorn src.api.app:app --host 0.0.0.0 --port 8000
```

This is the same process and command that serves `/api/v1/...`; there is no
separate workspace service to run.

## Interactive docs (Swagger)

FastAPI serves the generated OpenAPI docs automatically — with the server
running, open:

- `http://127.0.0.1:8000/docs` — Swagger UI (interactive, try-it-out)
- `http://127.0.0.1:8000/redoc` — ReDoc (read-only)
- `http://127.0.0.1:8000/openapi.json` — raw OpenAPI schema

Workspace routes are grouped under the `workspace` tag, alongside `health`,
`adapters`, `metadata`, `registrations`, and `registry`. Each route's error
status codes (401/409/428/…) are documented in the generated schema and
match the tables in this file.

Two caveats when trying routes out in Swagger UI:

1. Workspace routes require the registry GitHub session cookie. For
   `/sessions/{id}/...` requests, also provide the `authorization` field with
   `Bearer <session_token>` — the word `Bearer`, a space, then the token from
   `POST /sessions` — or put the bare token in the `token` query field.
2. Do not execute `GET .../events` from Swagger UI: it is an infinite SSE
   stream and the UI waits for the response to complete. Use `curl -N` (see
   the example below) or the frontend's SSE reader instead.

## Security model — read before deploying

**Run this service only inside the hardened container.** Sessions expose a
`run_command` tool to the model: arbitrary shell in the server's context. The
path confinement on file tools and file routes does *not* apply to shell
commands — on a bare host, a prompt-injected turn can read anything the
server's user can read and exfiltrate it. The docker-compose setup (read-only
root, non-root user, cap-drop, resource limits) is the intended boundary;
per-session sibling containers are the multi-tenant answer (deployment.md).

Consequences of the current single-process design:

- **Sessions are not isolated from each other at the shell level.** File
  tools and file routes are confined per workspace, but one session's
  `run_command` can read another session's workspace directory. Acceptable
  for a single-user demo; multi-tenant use requires per-session containers.
- **Session allocation is authenticated but uncapped.** Any signed-in user can
  create sessions (each: MCP connection + directory + task), and there is still
  no request-body limit or workspace disk quota.
- **Todo for sessions/requests**: Front nginx with rate limits,
  set `client_max_body_size`, and monitor disk usage before wider deployment.
- **TLS is a deployment requirement, not built in.** The BYOK key travels in
  a request body and the session token in a header; both need HTTPS
  termination (nginx) on anything but localhost. The token is accepted only
  in the `Authorization` header, never as a query parameter, so it does not
  land in access logs.

## Concepts

A **session** is one workspace: its own directory on disk, its own MCP
connection, its own conversation history, and its own user-supplied Anthropic
credential (BYOK). Sessions are independent; deleting a session destroys all
of it.

A **turn** is one user message plus everything the agent does in response
(thinking, tool calls, file edits, shell commands) until it produces its final
answer. Turns are serialized per session — one at a time.

The model only ever sees truncated tool results (`MCP_RESULT_MAX_CHARS`,
default 20000); full results stay in the backend. SSE events carry at most a
5000-char preview of each tool result.

Two knowable limits: conversation history grows unbounded with the session
(memory server-side, input tokens per turn — prompt caching softens the cost
but not the growth), so prefer fresh sessions over very long ones.

Error messages sent to clients are generic (`turn_error`, `session_error`,
the 502s, file-route errors) and never contain server paths or raw exception
text; the details are logged server-side.

## Authentication

`POST /sessions` requires the registry GitHub auth cookie and returns a
`session_token`. Every `/sessions/{id}/...` request requires that same GitHub
user plus the workspace token as

```
Authorization: Bearer <session_token>
```

There is no query-parameter form, so browser-native `EventSource` (which
cannot set headers) is not supported; use a `fetch()`-based SSE reader, as
the frontend does.

Unknown session ids, wrong users, and wrong tokens all return **401** with the
same body, so session ids and ownership cannot be enumerated.

## Endpoints

### Session lifecycle

#### `POST /sessions`

Creates a session: allocates the workspace directory and opens the MCP
connection.

- **201**
  ```json
  {
    "session_id": "e53d64ad54dc43f0aa3e321dc7f0f7d4",
    "session_token": "i_sFZ6s1NAoBB...",
    "model": "claude-opus-4-8",
    "tools": [
      {"name": "get_available_workflows", "description": "Main entry point tool ..."},
      {"name": "write_file", "description": "Create or overwrite a text file with the given content."}
    ]
  }
  ```
- **401** — GitHub sign-in is required(to start a session). The frontend prompts the user to sign in first too.
This is the same as the normal application authentication and differs from the 401 that is returned on other agentic
workspace routes, where 401 means the session workspace key is invalid instead.
- **502** — the MCP server could not be reached (session is not created).

The `session_token` is shown exactly once; store it client-side for the
session's lifetime.

#### `GET /sessions/{id}`

Session state — useful after a reconnect.

- **200**
  ```json
  {
    "session_id": "e53d...",
    "model": "claude-opus-4-8",
    "has_key": true,
    "busy": false,
    "error": null,
    "tools": [ ... ]
  }
  ```

`error` is non-null when the session's MCP connection died; such a session
only serves file routes and should be deleted.

#### `DELETE /sessions/{id}`

Ends the session: closes the MCP connection, drops the history, deletes the
workspace directory, forgets the key.

- **204**

### Key upload (BYOK)

#### `POST /sessions/{id}/key`

Attach the user's Anthropic credential to the session. The UI collects it in
the chat pane (masked input) but **must** send it here — never as a chat
message; anything in a chat message enters model context, history, and
provider logs. The backend holds the key in memory only and destroys it with
the session.

Body — one of:

```json
{"api_key": "sk-ant-..."}
{"auth_token": "<bearer token, e.g. for a gateway>"}
```

- **204** — stored.
- **400** — neither field given.

Calling it again replaces the credential.

### Chat

#### `POST /sessions/{id}/messages`

Append a user turn and start the tool loop. Returns immediately; progress
arrives on the events stream.

Body:

```json
{"content": "Create a BioCypher adapter for UniProt."}
```

- **202** — `{"turn_id": "1f0c..."}`
- **400** — empty `content`.
- **409** — a turn is already running; wait for `turn_done`/`turn_error`.
- **428** — no key set yet (`POST .../key` first).
- **502** — session unusable (MCP connection died).

If the turn fails mid-way (provider error, interrupt), the whole partial turn
is rolled back from history — the user simply retries.

#### `POST /sessions/{id}/interrupt`

Cancel the running turn. History rolls back to the pre-turn snapshot and a `turn_error` event
with message `"interrupted"` is emitted.

- **202** — `{"status": "interrupting"}`
- **409** — no turn is running.

#### `GET /sessions/{id}/events`

Server-sent events stream (`text/event-stream`). The first event is always a
snapshot:

```
event: session_state
data: {"has_key": false, "busy": false, "error": null}
```

then live events follow, each with an incrementing `id:`:

```
event: text_delta
id: 42
data: {"text": "Let me check the available workflows."}
```

A comment line `: heartbeat` is sent after 5 idle seconds to keep proxies
from closing the stream.

| Event | Data | Meaning |
|---|---|---|
| `session_state` | `{has_key, busy, error}` | snapshot on (re)connect |
| `turn_started` | `{turn_id}` | turn accepted by the worker |
| `thinking_started` | `{}` | model is in a thinking block (show a marker) |
| `text_delta` | `{text}` | assistant text, streamed |
| `tool_call` | `{name, args?}` | the model invoked a tool; `args` is omitted when empty |
| `tool_result` | `{name, is_error, chars, preview?}` | tool finished; `preview` is the first 500 chars when non-empty, `chars` the full length that entered model context |
| `usage` | `{input, cache_read, cache_write, output}` | token usage of one API call within the turn |
| `fs_changed` | `{paths}` | workspace changed (agent write/edit or any `run_command` — empty-string path means "anything may have changed"); refresh the tree and open files |
| `turn_done` | `{turn_id}` | turn finished; the session accepts the next message |
| `turn_error` | `{turn_id, message}` | turn failed or was interrupted; history rolled back |
| `session_error` | `{message}` | MCP connection died; session is unusable |
| `session_closed` | `{}` | session was deleted; the stream ends after this event |

Each session has one event stream: opening a new one ends the previous
stream, so a client that reconnects before the server has noticed its old
connection dropped is not locked out. A disconnected stream leaves its session
and workspace available for 60 seconds so the client can reconnect.

Reconnect with a `Last-Event-ID: <id>` header (the generated SSE client does
this automatically on retry) to have the events after `<id>` replayed right
after the `session_state` snapshot. The server keeps the last 5000 events per
session; events older than that are lost, and the snapshot is then the only
reliable state. Without the header, or on the first connect, nothing is
replayed — connect before sending messages.

### Files (directory pane + preview)

All `path` parameters are relative to the session workspace. Absolute paths
and `..` are rejected with **400**; symlink escapes are blocked server-side.

#### `GET /sessions/{id}/files?path=<dir>`

List one directory level (directories first, then files, both sorted).
Omit `path` (or pass `""`) for the workspace root.

- **200**
  ```json
  {
    "path": "",
    "entries": [
      {"name": "adapter", "path": "adapter", "is_dir": true},
      {"name": "README.md", "path": "README.md", "is_dir": false}
    ]
  }
  ```
- **404** — not a directory.

Build the tree by fetching levels lazily as the user expands them.

#### `GET /sessions/{id}/file?path=<file>`

- **200** — `{"path": "a.txt", "content": "..."}`
- **404** — no such file.
- **413** — file larger than 1 MB.
- **415** — not a text file.

The workspace API is read-only: ask the assistant in chat to create, change,
or delete files.

## Status code summary

| Code | Meaning here                                                                                             |
|---|----------------------------------------------------------------------------------------------------------|
| 400 | invalid input: bad path, empty message, key body without a key                                           |
| 401 | missing/wrong workspace session token, or unknown session id                                             |
| 409 | conflict: turn already running, no turn to interrupt, or filesystem error on a file route |
| 413 | file too large to preview (> 1 MB)                                                                       |
| 415 | binary file requested as text                                                                            |
| 428 | no API key set for the session yet                                                                       |
| 429 | user already holds `AGENT_MAX_SESSIONS_PER_USER` sessions                                                |
| 500 | workspace session could not be created                                                                    |
| 502 | MCP server unreachable / session's MCP connection died                                                   |

## Configuration (env vars)

| Variable | Default | Purpose |
|---|---|---|
| `AGENT_API_PREFIX` | `/agent/api/v1` | route prefix (registry nginx convention) |
| `AGENT_WORKSPACES_ROOT` | `./workspaces` | parent dir of per-session workspaces (`/app/data/workspaces` in the compose stacks) |
| `AGENT_SESSION_READY_TIMEOUT` | `30` | seconds to wait for MCP on session create |
| `AGENT_MAX_SESSIONS_PER_USER` | `3` | concurrent sessions per GitHub user |
| `AGENT_SANDBOX_USER` | unset (`sandbox` in the Docker image) | user `run_command` runs as via sudo; unset runs as the API user |
| `BIOCYPHER_MCP_URL` | `https://mcp.biocypher.org/mcp` | MCP server |
| `BIOCYPHER_MCP_AUTH_HEADER[_FILE]` | — | MCP auth header, read once at service start |
| `CLAUDE_MODEL` | `claude-opus-4-8` | model for all sessions |
| `ANTHROPIC_BASE_URL` | — | Anthropic-compatible endpoint (LiteLLM, llama.cpp) |
| `CLAUDE_THINKING` | auto | `adaptive`/`off` override |
| `MCP_RESULT_MAX_CHARS` | `20000` | tool-result cap before model context |

Note: the Anthropic key is *not* configured via environment — each session
receives its own key through `POST .../key`.

## Example: full session with curl

```bash
B=http://127.0.0.1:8000/agent/api/v1

# 1. create a session
CREATED=$(curl -s -X POST $B/sessions)
SID=$(echo "$CREATED" | jq -r .session_id)
TOK=$(echo "$CREATED" | jq -r .session_token)
AUTH="Authorization: Bearer $TOK"

# 2. watch events (separate terminal)
curl -sN "$B/sessions/$SID/events" -H "$AUTH"

# 3. upload the key, then chat
curl -s -X POST $B/sessions/$SID/key -H "$AUTH" -H "Content-Type: application/json" \
     -d '{"api_key": "sk-ant-..."}' -o /dev/null
curl -s -X POST $B/sessions/$SID/messages -H "$AUTH" -H "Content-Type: application/json" \
     -d '{"content": "What BioCypher workflows are available?"}'

# 4. browse the workspace;
curl -s "$B/sessions/$SID/files" -H "$AUTH"

# 5. clean up
curl -s -X DELETE $B/sessions/$SID -H "$AUTH"
```
