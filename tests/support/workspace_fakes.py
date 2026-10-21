"""Shared fakes for workspace service/API tests: MCP connector and Anthropic runner."""

from contextlib import asynccontextmanager
from types import SimpleNamespace

import anthropic
import httpx
from mcp.types import CallToolResult, TextContent, Tool


class FakeMcp:
    """Stands in for an initialized mcp.ClientSession."""

    def __init__(self):
        self.calls = []

    async def list_tools(self):
        return SimpleNamespace(
            tools=[
                Tool(
                    name="get_phase_guidance",
                    description="MCP guidance tool",
                    input_schema={"type": "object", "properties": {}},
                )
            ]
        )

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return CallToolResult(
            structured_content=None,
            content=[TextContent(type="text", text="mcp says hi")],
            is_error=False,
        )


@asynccontextmanager
async def fake_mcp_connect(url, headers):
    yield FakeMcp()


class FakeStream:
    """One assistant message: async context manager + event iterator."""

    def __init__(self, events, final):
        self.events = events
        self.final = final

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def __aiter__(self):
        async def gen():
            for event in self.events:
                yield event

        return gen()

    async def get_final_message(self):
        return self.final


def text_event(text):
    return SimpleNamespace(type="text", text=text)


def final_message(content, input_tokens=10, output_tokens=5):
    return SimpleNamespace(
        usage=SimpleNamespace(
            input_tokens=input_tokens,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
            output_tokens=output_tokens,
        ),
        content=content,
    )


class FakeRunner:
    """Mimics tool_runner: yields streams, hands out tool responses between."""

    def __init__(self, turns, error_at=None, error=None):
        # turns: list of (FakeStream, tool_response_dict_or_None)
        self.turns = turns
        self.error_at = error_at
        self.error = error
        self._responses = [resp for _, resp in turns]

    def __aiter__(self):
        async def gen():
            for i, (stream, _) in enumerate(self.turns):
                if self.error_at == i:
                    if self.error is not None:
                        raise self.error
                    request = httpx.Request("POST", "https://api.anthropic.test")
                    raise anthropic.APIError(
                        "LLM Provider (Anthropic) error - check if their services are down and try later",
                        request,
                        body=None,
                    )
                yield stream

        return gen()

    async def generate_tool_call_response(self):
        return self._responses.pop(0)


def fake_client_factory(runner):
    def factory(api_key=None, auth_token=None, timeout=None):
        return SimpleNamespace(
            beta=SimpleNamespace(
                messages=SimpleNamespace(tool_runner=lambda **kwargs: runner)
            )
        )

    return factory


def install_fake_sudo(monkeypatch):
    """Run "sandboxed" commands as the current user instead of via sudo.

    Exercises the sandboxed code paths (pool users, ``env --chdir``, the
    workspace_fs helper subprocess) without sudo or real pool users. Returns
    the list of ``(user, argv)`` calls. ``kill -1`` (kill every process of
    the user) and the shared-temp ``find -delete`` become no-ops: as the test
    user they would kill the test run and delete the test user's files.
    """
    from src.core.workspace import client_loop, workspace_fs

    calls = []

    def fake_sandbox_argv(argv, env, user, cwd=None):
        if not user:
            return argv
        calls.append((user, list(argv)))
        if argv[0] == "/bin/kill" and argv[-1] == "-1":
            return ["/bin/true"]
        if argv[0] == "/usr/bin/find":
            # Clearing the user's files in /tmp: as the test user it would
            # delete the test user's files.
            return ["/bin/true"]
        if argv[1:3] == ["-m", "venv"]:
            # A real venv takes seconds; only its bin dir is used.
            argv = ["/bin/mkdir", "-p", ".venv/bin"]
        prefix = ["/usr/bin/env", "-i"]
        if cwd is not None:
            prefix.append(f"--chdir={cwd}")
        return [*prefix, *(f"{k}={v}" for k, v in env.items()), *argv]

    monkeypatch.setattr(workspace_fs, "sandbox_argv", fake_sandbox_argv)
    monkeypatch.setattr(client_loop, "sandbox_argv", fake_sandbox_argv)
    return calls
