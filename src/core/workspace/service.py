"""Session service: the client-side tool loop lifted into per-session actors.

Each workspace session owns:

- a workspace directory (file tools and run_command are confined to it),
- when sandboxed, a pool user leased for the session's lifetime: the
  workspace belongs to that user (mode 0700) and every file operation and
  command of the session runs as it, so sessions cannot reach each other,
- a conversation history with the snapshot/rollback pattern per turn,
- an MCP connection living in a dedicated actor task (the asyncio context
  managers must be entered and exited by the same task),
- optionally a user-supplied Anthropic key/token (BYOK, held in memory only).

Turns are serialized per session: :meth:`Session.submit` starts at most one
turn task at a time; the actor task only owns the MCP connection. Progress is fanned out to SSE subscribers as events;
full tool results never leave this process (only truncated text enters model
context, and events carry a short preview).

``src.api.routers.workspace`` is the HTTP face over :class:`SessionManager`;
see ``docs/API.md`` for the route-level contract.
"""

from __future__ import annotations

import asyncio
import collections
import contextlib
import fcntl
import logging
import os
import pwd
import re
import secrets
import shutil
import sys
import time
import uuid
from pathlib import Path

import anthropic
import httpx
from anthropic import AsyncAnthropic

from src.core.workspace import client_loop as cl
from src.core.workspace import workspace_fs as wfs

logger = logging.getLogger(__name__)

# Seconds to wait for the MCP connection when creating a session.
READY_TIMEOUT = float(os.getenv("AGENT_SESSION_READY_TIMEOUT", "30"))
# Chars of each tool result included in the tool_result SSE event.
EVENT_PREVIEW_CHARS = 5000
# Max events buffered per SSE subscriber; oldest are dropped beyond this.
EVENT_QUEUE_SIZE = 1000
# Recent events kept per session for replay to a reconnecting stream
# (Last-Event-ID). A streamed answer is mostly text_delta events, so this
# covers a disconnect of some thousand deltas; older events are lost.
EVENT_REPLAY_SIZE = 5000
# Close idle sessions after 24 hours
IDLE_SESSION_SECONDS = 24 * 60 * 60  # gets overwritten in test
IDLE_REAPER_SECONDS = 5 * 60
# Seconds teardown waits for an interrupted turn to roll back.
TURN_STOP_TIMEOUT = 10
# Concurrent sessions one GitHub user may hold (each owns an MCP connection
# and a workspace directory).
MAX_SESSIONS_PER_USER = int(os.getenv("AGENT_MAX_SESSIONS_PER_USER", "3"))
# Sandbox user pool: <prefix>1 .. <prefix><size>, created in the Docker image.
# One user per active session, so the size is also the global session cap.
# Unset = unsandboxed: everything runs as the API user (local dev, tests).
SANDBOX_USER_PREFIX = os.getenv("AGENT_SANDBOX_USER_PREFIX", "")
SANDBOX_POOL_SIZE = int(os.getenv("AGENT_SANDBOX_POOL_SIZE", "0"))
# Directory names of session workspaces (uuid4 hex); the startup sweep removes
# nothing else from the workspaces root.
SESSION_DIR_RE = re.compile(r"[0-9a-f]{32}")
# Lock file in the workspaces root held by the one process that manages it.
LOCK_FILE = ".manager.lock"
# Shared temp directories a pool user may leave files in; cleared on release.
SHARED_TMP_DIRS = ("/tmp", "/var/tmp", "/dev/shm")
# Lower-cased error substrings meaning "key valid but out of money": Anthropic
# ("credit balance is too low") and OpenAI via LiteLLM ("insufficient_quota").
OUT_OF_CREDIT_MARKERS = ("credit balance is too low", "insufficient_quota")


class SessionStartupError(Exception):
    """MCP connection could not be established for a new session."""


class SessionLimitError(Exception):
    """The user already holds MAX_SESSIONS_PER_USER sessions."""


class SessionPoolExhaustedError(SessionLimitError):
    """Every sandbox user is leased: the service holds its maximum of sessions."""


class TurnInFlightError(Exception):
    """A turn is already running on this session."""


## I know these are quite obtuse but I just wanted to make the code clear without relying on Stream data classes or their defaults
class WorkspaceStorageError(Exception):
    """Workspace session directory could not be created. Specifically to capture this issue instead of erroring -->
    returning SSE disconnect on error, which I hypothesize to displayed as Network Error"""


# Default MCP connector; tests inject a fake with the same shape via
# Session.mcp_connect. The mcp>=2.0 bootstrap itself lives once in
# client_loop.open_mcp_session, shared with the CLI's main().
connect_mcp = cl.open_mcp_session


def _first_line(description: str | None) -> str:
    return description.strip().splitlines()[0] if description else ""


def _block_get(block, key, default=None):
    """Read a field from an SDK content block (object or plain dict)."""
    if isinstance(block, dict):
        return block.get(key, default)
    return getattr(block, key, default)


def _tool_result_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            _block_get(c, "text", "")
            for c in content
            if _block_get(c, "type") == "text"
        )
    return str(content)


# So that we display useful information on the frontend, not empty brackets.
def _has_tool_details(value: object) -> bool:
    if isinstance(value, str):
        return value.strip() not in ("", "{}", "[]")
    return value not in (None, {}, [])


def sandbox_pool() -> list[str]:
    """Pool user names from the environment; empty when unsandboxed."""
    if not SANDBOX_USER_PREFIX or SANDBOX_POOL_SIZE <= 0:
        return []
    return [f"{SANDBOX_USER_PREFIX}{i}" for i in range(1, SANDBOX_POOL_SIZE + 1)]


def _exec_bin(workspace: Path, user: str | None) -> Path:
    if user:
        return workspace / ".venv" / "bin"
    return Path(sys.executable).parent


async def _run_as(user: str, argv: list[str], cwd: Path) -> int:
    """Run a housekeeping command as ``user`` in ``cwd``; return its exit code."""
    env = cl._exec_env(home=cwd)
    proc = await asyncio.create_subprocess_exec(
        *cl.sandbox_argv(argv, env, user, cwd=cwd),
        # This process may not enter cwd (a workspace); its parent is the
        # workspaces root, which it owns.
        cwd=cwd.parent,
        env=env,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    return await proc.wait()


async def _make_workspace(workspace: Path, user: str | None) -> None:
    """Create a session directory; sandboxed, owned by ``user`` with a venv.

    Sandboxed, ``user`` creates the directory itself (mode 0700) in the
    sticky, group-writable workspaces root, so only it can enter the
    workspace and nobody else can rename or delete it. It may not write to
    the service's own venv (that would let model commands change the running
    API), so pip installs go to ``.venv`` inside the workspace.
    """
    if not user:
        # mkdir is a blocking syscall; off-thread so one session's filesystem
        # latency (or a slow/networked workspaces_root) can't stall every
        # other session's SSE heartbeats and message dispatch on this loop.
        await asyncio.to_thread(workspace.mkdir)
        return
    if await _run_as(
        user, ["/bin/mkdir", "-m", "700", str(workspace)], workspace.parent
    ):
        raise OSError(f"could not create the session workspace {workspace}")
    if await _run_as(user, ["/bin/mkdir", wfs.TMP_DIR], workspace):
        raise OSError(f"could not create the session temp dir in {workspace}")
    if await _run_as(user, [sys.executable, "-m", "venv", ".venv"], workspace):
        raise OSError(f"could not create the session venv in {workspace}")


async def _remove_workspace(workspace: Path, user: str | None) -> bool:
    """Delete a workspace; True if it is gone afterwards.

    Sandboxed, first kill everything still running as ``user`` (e.g. commands
    started in the background) and delete its files in the shared temp
    directories, so nothing of this session survives into the next session
    that leases the same user; then let the owner restore access to and
    remove its files.
    """
    if user:
        await _run_as(user, ["/bin/kill", "-KILL", "-1"], workspace.parent)
        await _run_as(
            user,
            [
                "/usr/bin/find",
                *SHARED_TMP_DIRS,
                "-xdev",
                "-mindepth",
                "1",
                "-user",
                user,
                "-delete",
            ],
            workspace.parent,
        )
        await _run_as(
            user,
            ["/bin/sh", "-c", 'chmod -R u+rwX "$1"; rm -rf "$1"', "sh", str(workspace)],
            workspace.parent,
        )
    # Recursive delete is a blocking syscall storm on a large/full workspace;
    # off-thread for the same reason as the mkdir in _make_workspace.
    await asyncio.to_thread(shutil.rmtree, workspace, ignore_errors=True)
    return not await asyncio.to_thread(os.path.lexists, workspace)


def _owner_name(path: Path) -> str | None:
    try:
        return pwd.getpwuid(path.lstat().st_uid).pw_name
    except (KeyError, OSError):
        return None


def _put_dropping_oldest(queue: asyncio.Queue, item) -> None:
    # Bounded queue: a stalled SSE consumer must not grow memory for the
    # session's lifetime; the oldest event is the cheapest one to drop (a
    # reconnecting stream gets it back from the replay buffer).
    while True:
        try:
            queue.put_nowait(item)
            return
        except asyncio.QueueFull:
            with contextlib.suppress(asyncio.QueueEmpty):
                queue.get_nowait()


class Session:
    def __init__(
        self,
        session_id: str,
        owner_github_user_id: str,
        workspace: Path,
        mcp_url: str,
        mcp_headers: dict[str, str],
        sandbox_user: str | None = None,
    ):
        self.id = session_id
        self.owner_github_user_id = owner_github_user_id
        self.token = secrets.token_urlsafe(32)
        self.workspace = workspace
        self.sandbox_user = sandbox_user
        self.mcp_url = mcp_url
        self.mcp_headers = mcp_headers
        self.history: list = []
        self.api_key: str | None = None
        self.auth_token: str | None = None
        self.tools: list = []
        self.tool_defs: list[dict] = []
        self.subscribers: set[asyncio.Queue] = set()
        self.recent_events: collections.deque[dict] = collections.deque(
            maxlen=EVENT_REPLAY_SIZE
        )
        self.ready = asyncio.Event()
        # Set to make the actor leave the MCP context and finish.
        self.closed = asyncio.Event()
        self.error: str | None = None
        self.turn_task: asyncio.Task | None = None
        self.actor: asyncio.Task | None = None
        self.last_activity = time.monotonic()
        self._seq = 0
        # Test seams; the API layer never touches these.
        self.client_factory = AsyncAnthropic
        self.mcp_connect = connect_mcp
        self.file_tools = cl.make_file_tools(
            get_fs=lambda: self.fs,
            # No interactive env prompt like in the CLI: sandboxed sessions
            # get their own venv, unsandboxed ones share the service's.
            get_exec_bin=lambda: _exec_bin(self.workspace, self.sandbox_user),
            on_fs_change=self._on_fs_change,
        )

    @property
    def fs(self) -> wfs.WorkspaceFS:
        """File access to this session's workspace, as its sandbox user."""
        return wfs.WorkspaceFS(self.workspace, self.sandbox_user)

    @property
    def busy(self) -> bool:
        return self.turn_task is not None and not self.turn_task.done()

    @property
    def has_key(self) -> bool:
        return bool(self.api_key or self.auth_token)

    def set_key(self, api_key: str | None, auth_token: str | None) -> None:
        self.api_key = api_key or None
        self.auth_token = auth_token or None

    # Call this elsewhere to keep the workspace session alive, needed because otherwise SSE heartbeats would keep alive based on solely requests
    def mark_active(self) -> None:
        self.last_activity = time.monotonic()

    # ---------------------------------------------------------- events

    def publish(self, event_type: str, **data) -> None:
        self.mark_active()
        self._seq += 1
        event = {"seq": self._seq, "type": event_type, "data": data}
        self.recent_events.append(event)
        for queue in tuple(self.subscribers):
            _put_dropping_oldest(queue, event)

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=EVENT_QUEUE_SIZE)
        self.subscribers.add(queue)
        return queue

    def events_after(self, seq: int) -> list[dict]:
        """Buffered events newer than ``seq`` (oldest first)."""
        if seq >= self._seq:
            return []
        return [e for e in self.recent_events if e["seq"] > seq]

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self.subscribers.discard(queue)

    def _on_fs_change(self, path: str) -> None:
        self.publish("fs_changed", paths=[path])

    # ----------------------------------------------------------- actor

    async def run_actor(self) -> None:
        """Own the MCP connection until the session is closed.

        The streamable-HTTP context managers must be entered and exited by
        the same task; ``call_tool`` itself works from any task, so turns run
        in their own tasks (see :meth:`submit`).
        """
        try:
            async with self.mcp_connect(self.mcp_url, self.mcp_headers) as mcp:
                listed = await mcp.list_tools()
                self.tools = [
                    cl.make_tool(t, mcp) for t in listed.tools
                ] + self.file_tools
                self.tool_defs = [
                    {"name": t.name, "description": _first_line(t.description)}
                    for t in list(listed.tools) + self.file_tools
                ]
                self.ready.set()
                await self.closed.wait()
        except Exception:
            # Broad by design: the session becomes unusable. The details
            # (URLs, internal host names) go to the log only; clients see a
            # generic reason.
            logger.exception("MCP connection failed: session_id=%s", self.id)
            self.error = (
                "MCP connection lost"
                if self.ready.is_set()
                else "could not connect to MCP server"
            )
            self.ready.set()
            # A running turn would only fail on the dead MCP connection.
            self.interrupt()
            self.publish("session_error", message=self.error)

    def submit(self, content: str) -> str:
        """Start a turn and return its id; raise TurnInFlightError if busy."""
        if self.busy:
            raise TurnInFlightError
        turn_id = uuid.uuid4().hex
        self.turn_task = asyncio.create_task(self._run_turn(turn_id, content))
        return turn_id

    async def _run_turn(self, turn_id: str, content: str) -> None:
        self.publish("turn_started", turn_id=turn_id)
        snapshot = len(self.history)
        self.history.append({"role": "user", "content": content})
        client = self.client_factory(
            api_key=self.api_key,
            auth_token=self.auth_token,
            timeout=httpx.Timeout(
                timeout=600, connect=60
            ),  # Connect default is 5s and could be a cause of disconnects
        )
        runner = client.beta.messages.tool_runner(
            model=cl.MODEL,
            max_tokens=cl.MAX_TOKENS,
            system=cl.build_system_prompt(self.workspace, cl.RESULT_MAX_CHARS),
            tools=self.tools,
            messages=self.history,
            stream=True,
            **cl.optional_request_params(),
        )
        try:
            async for stream in runner:
                async with stream:
                    await self._emit_stream(stream)
                    message = await stream.get_final_message()
                self._publish_usage(message.usage)
                self.history.append({"role": "assistant", "content": message.content})
                names_by_id = self._publish_tool_calls(message.content)
                tool_response = await runner.generate_tool_call_response()
                if tool_response is not None:
                    self.history.append(tool_response)
                    self._publish_tool_results(tool_response, names_by_id)
            # No await after the terminal event: the task is done (busy is
            # False) before any client can react to turn_done.
            self.publish("turn_done", turn_id=turn_id)
        except asyncio.CancelledError:
            self._fail_turn(snapshot, turn_id, "interrupted")
            raise
        except anthropic.APIError as error:
            # Same rationale as the CLI: a partial turn can leave a tool_use
            # without its tool_result, which would 400 on every next request.
            # Extra logging as this has been hard to debug before:
            logger.exception("Workspace provider stream failed for turn %s", turn_id)
            message = "Error from AI model stream. Please try again."
            if isinstance(error, anthropic.AuthenticationError):
                message = "Your API key was rejected. Check it or use another key."
            elif any(marker in str(error).lower() for marker in OUT_OF_CREDIT_MARKERS):
                message = (
                    "Your API key is out of credit. Add credit or use another key."
                )
            self._fail_turn(snapshot, turn_id, message)
        except Exception:
            # Any other failure is confined to this turn: same rollback, and
            # the session (and its MCP connection) stays usable. Without this
            # the exception would propagate into run_actor and kill the
            # session with a dangling user message in history.
            logger.exception("Workspace turn failed for turn %s", turn_id)
            self._fail_turn(
                snapshot, turn_id, "Workspace turn failed. Please try again."
            )

    def _fail_turn(self, snapshot: int, turn_id: str, message: str) -> None:
        """Roll the partial turn back and report it; the session stays usable."""
        del self.history[snapshot:]
        self.publish("turn_error", turn_id=turn_id, message=message)

    def _publish_usage(self, usage) -> None:
        self.publish(
            "usage",
            input=usage.input_tokens,
            cache_read=usage.cache_read_input_tokens,
            cache_write=usage.cache_creation_input_tokens,
            output=usage.output_tokens,
        )

    def _publish_tool_calls(self, content) -> dict:
        """Emit tool_call events; map tool_use ids to names for the results."""
        names_by_id = {}
        for block in content:
            if _block_get(block, "type") == "tool_use":
                names_by_id[_block_get(block, "id")] = _block_get(block, "name")
                details = {"name": _block_get(block, "name")}
                tool_input = _block_get(block, "input")
                if _has_tool_details(tool_input):
                    details["args"] = tool_input
                # otherwise, if there were no args, just display the tool name in the frontend
                self.publish("tool_call", **details)
        return names_by_id

    def _publish_tool_results(self, tool_response, names_by_id: dict) -> None:
        for block in _block_get(tool_response, "content", []):
            if _block_get(block, "type") != "tool_result":
                continue
            text = _tool_result_text(_block_get(block, "content", ""))
            friendly_text = (
                text.replace("[exit 0]", "[Succeeded]")
                .replace("[exit 1]", "[Errored]")
                .replace("[exit 2]", "[Command usage error]")
            )
            details = {
                "name": names_by_id.get(_block_get(block, "tool_use_id")),
                "is_error": bool(_block_get(block, "is_error", False)),
                "chars": len(text),
            }
            preview = friendly_text[:EVENT_PREVIEW_CHARS]
            if _has_tool_details(preview):
                details["preview"] = preview
            self.publish("tool_result", **details)

    async def _emit_stream(self, stream) -> None:
        thinking_marked = False
        async for event in stream:
            if event.type == "text":
                self.publish("text_delta", text=event.text)
            elif event.type == "thinking" and not thinking_marked:
                self.publish("thinking_started")
                thinking_marked = True

    def interrupt(self) -> bool:
        if self.busy:
            self.turn_task.cancel()
            return True
        return False


class SessionManager:
    def __init__(
        self,
        workspaces_root: Path | str | None = None,
        mcp_url: str | None = None,
        mcp_headers: dict[str, str] | None = None,
        mcp_connect=None,
        sandbox_users: list[str] | None = None,
    ):
        self.workspaces_root = Path(
            workspaces_root or os.getenv("AGENT_WORKSPACES_ROOT", "workspaces")
        ).resolve()
        self.mcp_url = mcp_url or cl.MCP_URL
        # Read once for the whole service: read_secret scrubs the env var,
        # so per-session reads would only work for the first session.
        self.mcp_headers = cl.mcp_headers() if mcp_headers is None else mcp_headers
        self.mcp_connect = mcp_connect
        self.sessions: dict[str, Session] = {}
        self._pending_creates: collections.Counter[str] = collections.Counter()
        pool = sandbox_pool() if sandbox_users is None else list(sandbox_users)
        self.sandboxed = bool(pool)
        self._free_users: collections.deque[str] = collections.deque(pool)
        self._leased_users: set[str] = set()
        # False when another process manages this workspaces root (see
        # startup); then this one creates no sessions.
        self._serving = True
        self._lock_fd: int | None = None
        self._sse_disconnect_tasks: dict[str, asyncio.Task[None]] = {}

    async def create(self, *, owner_github_user_id: str) -> Session:
        if not self._serving:
            raise SessionPoolExhaustedError
        owned = sum(
            s.owner_github_user_id == owner_github_user_id
            for s in self.sessions.values()
        )
        if owned + self._pending_creates[owner_github_user_id] >= MAX_SESSIONS_PER_USER:
            raise SessionLimitError
        # Lease before the first await, for the same reason as the reservation
        # below; _create_session hands the user back if creation fails.
        sandbox_user = self._lease_user()
        # Increment immediately/Reserve before the await so simultaneous invocations of session creation cannot be made at the same time
        self._pending_creates[owner_github_user_id] += 1
        try:
            return await self._create_session(
                owner_github_user_id=owner_github_user_id, sandbox_user=sandbox_user
            )
        finally:
            self._pending_creates[owner_github_user_id] -= 1
            # on error or normal successful end, reset the users count
            if not self._pending_creates[owner_github_user_id]:
                del self._pending_creates[owner_github_user_id]

    def _lease_user(self) -> str | None:
        """Take a free pool user; None when unsandboxed."""
        if not self.sandboxed:
            return None
        if not self._free_users:
            raise SessionPoolExhaustedError
        user = self._free_users.popleft()
        self._leased_users.add(user)
        return user

    def _release_user(self, user: str | None, reusable: bool) -> None:
        """Return a leased user to the pool.

        A user that is not ``reusable`` stays out of the pool: its workspace
        could not be removed, or its session's turn may still run commands
        as it, and the next session leasing it could see either.
        """
        if user is None or user not in self._leased_users:
            return
        self._leased_users.discard(user)
        if reusable:
            self._free_users.append(user)
        else:
            logger.error("sandbox user %s withheld from the pool", user)

    async def _remove_and_release(
        self, workspace: Path, user: str | None, reusable: bool = True
    ) -> None:
        """Remove a workspace, then release its user even if removal raised."""
        removed = False
        try:
            removed = await _remove_workspace(workspace, user)
            if not removed:
                logger.error("could not remove workspace %s", workspace.name)
        finally:
            self._release_user(user, reusable and removed)

    async def _create_session(
        self, *, owner_github_user_id: str, sandbox_user: str | None
    ) -> Session:
        """Originally this was in the create function above, separated out
        so we can prevent concurrent creates"""
        try:
            await asyncio.to_thread(
                self.workspaces_root.mkdir, parents=True, exist_ok=True
            )
        except BaseException as e:
            self._release_user(sandbox_user, reusable=True)
            if isinstance(e, OSError):
                logger.exception("Could not create workspace root")
                raise WorkspaceStorageError from e
            raise
        session_id = uuid.uuid4().hex
        workspace = self.workspaces_root / session_id
        try:
            await _make_workspace(workspace, sandbox_user)
        except BaseException as e:
            # Also on cancellation: to_thread's worker thread runs mkdir to
            # completion even if this await is cancelled (e.g. task killed on
            # shutdown), so the dir can land on disk with nothing left to
            # track/clean it. Nothing references `session` yet, so clean up
            # here before propagating.
            await self._remove_and_release(workspace, sandbox_user)
            if isinstance(e, OSError):
                logger.exception("Could not create workspace directory")
                raise WorkspaceStorageError from e
            raise
        session = Session(
            session_id,
            owner_github_user_id,
            workspace,
            self.mcp_url,
            self.mcp_headers,
            sandbox_user,
        )  # same authentication as using Github login for registering adapters
        if self.mcp_connect is not None:
            session.mcp_connect = self.mcp_connect
        session.actor = asyncio.create_task(session.run_actor())
        try:
            await asyncio.wait_for(session.ready.wait(), timeout=READY_TIMEOUT)
        except TimeoutError:
            session.error = f"MCP connection timed out after {READY_TIMEOUT}s"
        except BaseException:
            # Same hazard: cancelled here and the session isn't registered in
            # self.sessions yet, so it's on us to tear down the actor/dir.
            await self._teardown(session)
            raise
        if session.error:
            await self._teardown(session)
            raise SessionStartupError(session.error)
        self.sessions[session.id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        return self.sessions.get(session_id)

    def open_event_stream(
        self, session: Session, last_event_id: int | None = None
    ) -> tuple[asyncio.Queue, list[dict]]:
        """Subscribe the session's only event stream.

        Returns the live queue and, for a reconnect with ``last_event_id``,
        the buffered events the client missed. Both are taken without an
        await in between, so nothing is lost or delivered twice.

        A still-open older stream is ended (``None`` on its queue): a client
        reconnects before the server notices its old connection dropped, and
        the session belongs to one browser tab anyway.
        """
        for old in tuple(session.subscribers):
            session.unsubscribe(old)
            _put_dropping_oldest(old, None)
        # Reconnection cancels the short cleanup window.
        self._cancel_sse_disconnect(session.id)
        backlog = [] if last_event_id is None else session.events_after(last_event_id)
        return session.subscribe(), backlog

    def close_event_stream(self, session: Session, queue: asyncio.Queue) -> None:
        session.unsubscribe(queue)
        if self.get(session.id) is session and not session.subscribers:
            self._schedule_sse_disconnect(session.id)

    # New event stream or deletion stops the scheduled cleanup task.
    def _cancel_sse_disconnect(self, session_id: str) -> None:
        task = self._sse_disconnect_tasks.pop(session_id, None)
        if task is not None and task is not asyncio.current_task():
            task.cancel()

    # schedule for deletion in 60 seconds time (that is controlled by _delete_after_sse_grace)
    def _schedule_sse_disconnect(self, session_id: str) -> None:
        self._cancel_sse_disconnect(session_id)
        task = asyncio.create_task(self._delete_after_sse_60_second_timeout(session_id))
        self._sse_disconnect_tasks[session_id] = task

    # Delete only if the session still has no active event stream after 60 seconds
    async def _delete_after_sse_60_second_timeout(self, session_id: str) -> None:
        try:
            await asyncio.sleep(60)
            session = self.get(session_id)
            if session is not None and not session.subscribers:
                await self.delete(session_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("SSE reconnect cleanup failed: session_id=%s", session_id)
        finally:
            if self._sse_disconnect_tasks.get(session_id) is asyncio.current_task():
                self._sse_disconnect_tasks.pop(session_id, None)

    async def delete(self, session_id: str) -> bool:
        self._cancel_sse_disconnect(session_id)
        session = self.sessions.pop(session_id, None)
        if session is None:
            return False
        await self._teardown(session)
        return True

    # End idle sessions using normal deletion process which removes the API key and ends streams "nicely".
    async def reap_idle_sessions(self) -> int:
        now = time.monotonic()
        idle_session_ids = [
            session.id
            for session in self.sessions.values()
            if now - session.last_activity >= IDLE_SESSION_SECONDS
        ]
        deleted = await asyncio.gather(
            *(self.delete(session_id) for session_id in idle_session_ids)
        )
        return sum(deleted)

    # Stop any sessions which have been running for > 24 hours.
    async def run_idle_reaper(self) -> None:
        while True:
            await asyncio.sleep(IDLE_REAPER_SECONDS)
            try:
                await self.reap_idle_sessions()
            except Exception:
                logger.exception("workspace idle-session cleanup failed")

    async def _teardown(self, session: Session) -> None:
        session.set_key(None, None)
        if session.interrupt():
            # Let the turn roll back before its workspace disappears.
            await asyncio.wait({session.turn_task}, timeout=TURN_STOP_TIMEOUT)
        # A turn that outlived the wait could still run tools as the sandbox
        # user, so that user must not go to another session.
        turn_finished = session.turn_task is None or session.turn_task.done()
        session.closed.set()
        if session.actor is not None and not session.actor.done():
            try:
                await asyncio.wait_for(session.actor, timeout=10)
            except Exception:  # noqa: BLE001 - best-effort teardown; any actor
                # failure (timeout or otherwise) still needs the cancel below
                session.actor.cancel()
                with contextlib.suppress(Exception, asyncio.CancelledError):
                    await session.actor
        # Tell open SSE streams the session is gone — they end on this event
        # instead of heartbeating a dead session forever.
        session.publish("session_closed")
        session.subscribers.clear()
        await self._remove_and_release(
            session.workspace, session.sandbox_user, reusable=turn_finished
        )

    async def startup(self) -> None:
        """Prepare the workspaces root; call once before serving sessions.

        Takes the root's lock (one managing process per root: separate
        processes would lease the same pool users and sweep each other's
        live workspaces), drops pool users missing from the system, and
        removes workspaces orphaned by a crash. Never raises: a failure here
        disables the workspace feature, not the API.
        """
        try:
            await asyncio.to_thread(
                self.workspaces_root.mkdir, parents=True, exist_ok=True
            )
            self._lock_fd = os.open(
                self.workspaces_root / LOCK_FILE, os.O_RDWR | os.O_CREAT, 0o600
            )
            fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            logger.exception(
                "workspaces root %s unusable or managed by another process "
                "(run a single worker); workspace sessions disabled",
                self.workspaces_root,
            )
            self._serving = False
            return
        self._check_sandbox_pool()
        await self.sweep_orphaned_workspaces()

    def _check_sandbox_pool(self) -> None:
        """Drop pool users that do not exist (pool size above the image's)."""
        missing = []
        for user in tuple(self._free_users):
            try:
                pwd.getpwnam(user)
            except KeyError:
                missing.append(user)
                self._free_users.remove(user)
        if missing:
            logger.error(
                "sandbox users missing from the system, left out of the pool: %s",
                ", ".join(missing),
            )

    async def sweep_orphaned_workspaces(self) -> int:
        """Remove workspaces left behind by a crash or restart.

        Leases live in memory, so after a restart every pool user is free
        again; a leftover workspace must not stay readable by whichever
        session leases its owner next. Only session directories are touched.
        Logs instead of raising. Returns the number of workspaces removed.
        """
        try:
            entries = await asyncio.to_thread(
                lambda: list(self.workspaces_root.iterdir())
            )
        except FileNotFoundError:
            return 0
        except OSError:
            logger.exception("could not list the workspaces root")
            return 0
        pool = set(self._free_users) | self._leased_users
        removed = 0
        for entry in entries:
            if not SESSION_DIR_RE.fullmatch(entry.name) or entry.name in self.sessions:
                continue
            owner = _owner_name(entry)
            try:
                gone = await _remove_workspace(entry, owner if owner in pool else None)
            except OSError:
                logger.exception("could not remove orphaned workspace %s", entry.name)
                gone = False
            if gone:
                removed += 1
                continue
            logger.error("could not remove orphaned workspace %s", entry.name)
            # Same rule as _release_user: its owner must not be leased.
            with contextlib.suppress(ValueError):
                self._free_users.remove(owner)
        return removed

    async def shutdown(self) -> None:
        # delete() pops from self.sessions synchronously before its first
        # await, so concurrent delete()s racing over the same dict is safe.
        session_ids = list(self.sessions)
        results = await asyncio.gather(
            *(self.delete(session_id) for session_id in session_ids),
            return_exceptions=True,
        )
        for session_id, result in zip(session_ids, results):
            if isinstance(result, BaseException):
                logger.error(
                    "session teardown failed during shutdown: session_id=%s",
                    session_id,
                    exc_info=result,
                )
        if self._lock_fd is not None:
            os.close(self._lock_fd)
            self._lock_fd = None
