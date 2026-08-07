# Agentic workspace

The agentic workspace facilitates adapter creation using AI agents and the [BioCypher MCP](https://github.com/biocypher/biocypher-mcp). Currently only Anthropic (Claude) can be used for this, and it requires the user to have an API key. It is planned to extend this to BYOK, however the best integration of MCP is currently with Claude.

## `client_loop.py`

Install the workspace dependencies and run the client from the repository root using

    uv sync
    uv run python src/core/workspace/client_loop.py

You need to provide your Anthropic API key via one of:

    export ANTHROPIC_API_KEY="<your key>"
    # or
    export ANTHROPIC_API_KEY_FILE="secrets/anthropic_api_key"
You will first need to confirm the Python environment that should be used for the adapter development. This will be a different environment to the registry environment, so you need to set it up first and install BioCypher and cookiecutter. I use my standard BioCypher environment at the moment.

The reason that I have set up the script like this - asking for the environment - is that there are many ways to create and use environments. We want to limit the choices for the registry and use a dedicated environment for the agentic workspace processes. Also it uses additional tokens if you first need to create a new environment which is unnecessary for this use case and can be shipped with the container.

The `client_loop` script starts the middleman process between two independent connections:

you (terminal)->  
    -> client_loop.py - HTTPS -> Anthropic API (or local endpoint)  [LLM]  
    -> streamable HTTP - https://mcp.biocypher.org/mcp      [MCP server]  

The LLM never talks directly to the MCP. The MCP never talks directly to the LLM. The process started via `client_loop.py` is only the bridge and constitutes the "client-side tool loop": The Anthropic remote-MCP connector is not used (that would be the LLM directly talking to the MCP and to the client, with no direct connection between client and MCP). The purpose of this separation lies in, that users may have sensitive or proprietary data that should not be shared beyond the local network. At the current stage the data confidentiality is not complete as user messages get appended to the history.

| Data | Reaches Anthropic | Reaches MCP server | Stays local |
|---|---|---|---|
| User input / pastes | always, every request | if model copies into tool args | — |
| Tool arguments | yes (they're model output, also echoed back in history) | yes | — |
| Full MCP results | first `RESULT_MAX_CHARS` only | originate there | truncated tail |
| File tool content | args + truncated results, yes | no | file bytes on disk |

For full data privacy:
1. Use a local model. 
2. Route the data around the model and only provide pointers. This can be achieved by adding a local tool like `profile_data(path)`: reads file locally, computes schema/column names/dtypes/sample stats and returns only that to the context. 

## The MCP

The MCP provides access to custom tools that allow an effective and efficient creation of BioCypher adapters. It empowers the agentic loop with specific tools.

 ### Data flow per turn

1. User types message that is appended to history.
2. `client.beta.messages.tool_runner()` sends the message to the LLM: system prompt + tool schemas + full history, and streams the response.
3. If the LLM emits tool_use block, the runner calls matching wrapped function locally in your process:
    - MCP tool: `call()` → `session.call_tool()` → HTTP request to BioCypher server. Arguments the LLM chose go to MCP server — that is where data passed to MCP goes: over HTTPS to mcp.biocypher.org (or your BIOCYPHER_MCP_URL).
    - File tool: runs on local disk, nothing leaves machine.
4. Result comes back to your process. `render_tool_result()` flattens to text. Truncated at `RESULT_MAX_CHARS` (20k default). Full result stays local; only truncated text goes back to Anthropic as tool_result message.
5. Runner loops: sends history + tool result back to LLM, LLM continues. Repeats until no more tool calls.
6. history mirrors runner conversation so next user turn keeps full context.
7. On API error mid-loop: del history[snapshot:] — drops whole partial turn. Reason: assistant tool_use without matching tool_result = 400 on every later request.
So the current privacy shape is: user text + tool arguments + truncated tool results → Anthropic. Tool arguments → MCP server. Raw full tool results → nowhere, die in process memory.

 ## LLM connection

- `AsyncAnthropic()`: SDK reads `ANTHROPIC_API_KEY` + `ANTHROPIC_BASE_URL` from env. Here could be a swap mechanism: point the base URL at LiteLLM proxy or llama.cpp server with Anthropic-compatible API, the key then becomes a dummy value.
- Model from `CLAUDE_MODEL`, default `claude-opus-4-8`.
- `thinking_config()`: adaptive thinking on when talking to real Anthropic, off for local endpoints as they may reject parameters. Override with `CLAUDE_THINKING`.
- Each turn is a fresh stateless API request with no server-side session. The full history is re-sent every time — that is why caching matters.

## Token use

Four numbers are printed per LLM round-trip: `input_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`, `output_tokens`.

- The input grows every turn. Stateless API: each request re-sends system prompt + all tool schemas + entire history including all past tool results; so a long chat results in a big input.
- Prompt caching fights that. `cache_control={"type": "ephemeral"}` sets the auto-cache prefix. Turn N writes prefix to cache (`cache_write`), turn N+1 reads it (`cache_read`). Cache reads are billed at ~10% of normal input rate, writes at ~125%. So in a steady chat: most tokens show up as cheap cache_read, only new turn as full-price input.
    - One user message can mean many LLM calls. Each tool call = extra round trip (assistant `tool_use` → `tool_result` → next request). 5 tool calls = 6 API requests, each re-reading whole context. Cache makes that survivable.
    - `RESULT_MAX_CHARS` = biggest token lever. MCP results can be huge; truncation caps what enters context at 20k chars (~5k tokens). System prompt tells model: result cut off → narrow arguments, don't repeat call.
    - Output capped `max_tokens=16000` per response. Thinking tokens count as output when adaptive thinking on.

One caveat: `cache_control={"type": "ephemeral"}` as top-level kwarg — that is the SDK's auto-prefix-caching convenience on the tool runner. Works with real Anthropic; local endpoints (LiteLLM/llama.cpp) may ignore or reject it, same class of issue as thinking param but no env toggle guards it here.

# Still missing at this point
- API integration. Will happen in the next step as a merger from the [agentic-workspace](https://github.com/iulusoy/agentic-workspace) repo.
- Deployment integration. This can be run via a container, and then spawn its own per-session containers (see [deployment](./deployment.md)).
- Frontend integration. Will happen after API and deployment integration and then lead to iterations over backend, API, and deployment.
- Integration of neo4j graphs into the registry, to show the built graph or at least metagraph for the adapter. Requires the metagraph backend of BioCypher.
- Creation of croissant files for the adapter. Requires adapting the cookiecutter repo.
- Multiple MCPs. We also want at least OntoWeaver MCP to run as well.
- Problem with Anthropic API keys and testing the performance of local models.
- Integration with GitHub: Creating repos on GitHub with the folders created in a session.