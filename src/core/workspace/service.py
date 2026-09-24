"""Session service: the client-side tool loop lifted into per-session actors.

Each workspace session owns:

- a workspace directory (file tools and run_command are confined to it),
- a conversation history with the snapshot/rollback pattern per turn,
- an MCP connection living in a dedicated actor task (the asyncio context
  managers must be entered and exited by the same task),
- optionally a user-supplied Anthropic key/token (BYOK, held in memory only).

Turns are serialized per session: the actor consumes one message at a time
from the session inbox. Progress is fanned out to SSE subscribers as events;
full tool results never leave this process (only truncated text enters model
context, and events carry a short preview).

``src.api.routers.workspace`` is the HTTP face over :class:`SessionManager`;
see ``docs/API.md`` for the route-level contract.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
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

logger = logging.getLogger(__name__)

# Seconds to wait for the MCP connection when creating a session.
READY_TIMEOUT = float(os.getenv("AGENT_SESSION_READY_TIMEOUT", "30"))
# Chars of each tool result included in the tool_result SSE event.
EVENT_PREVIEW_CHARS = 5000
# Max events buffered per SSE subscriber; oldest are dropped beyond this.
EVENT_QUEUE_SIZE = 1000
# Close idle sessions after 24 hours
IDLE_SESSION_SECONDS = 24 * 60 * 60  # gets overwritten in test
IDLE_REAPER_SECONDS = 5 * 60
# Concurrent sessions one GitHub user may hold (each owns an MCP connection
# and a workspace directory).
MAX_SESSIONS_PER_USER = int(os.getenv("AGENT_MAX_SESSIONS_PER_USER", "3"))


class SessionStartupError(Exception):
    """MCP connection could not be established for a new session."""


class SessionLimitError(Exception):
    """The user already holds MAX_SESSIONS_PER_USER sessions."""


## I know these are quite obtuse but I just wanted to make the code clear without relying on Stream data classes or their defaults
class WorkspaceStorageError(Exception):
    """Workspace session directory could not be created. Specifically to capture this issue instead of erroring -->
    returning SSE disconnect on error, which I hypothesize to displayed as Network Error"""


class EventStreamAlreadyActive:
    """A workspace session already has an active event stream."""


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


def _exec_bin(workspace: Path) -> Path:
    if cl.SANDBOX_USER:
        return workspace / ".venv" / "bin"
    return Path(sys.executable).parent


async def _run_as_sandbox(argv: list[str], cwd: Path) -> int:
    """Run a housekeeping command as the sandbox user; return its exit code."""
    env = cl._exec_env(home=cwd)
    proc = await asyncio.create_subprocess_exec(
        *cl.sandbox_argv(argv, env, cl.SANDBOX_USER),
        cwd=cwd,
        env=env,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    return await proc.wait()


async def _make_workspace(workspace: Path) -> None:
    """Create a session directory; sandboxed, also its private venv.

    The sandbox user may not write to the service's own venv (that would let
    model commands change the running API), so pip installs go to
    ``.venv`` inside the workspace, created as the sandbox user.
    """
    # mkdir is a blocking syscall; off-thread so one session's filesystem
    # latency (or a slow/networked workspaces_root) can't stall every other
    # session's SSE heartbeats and message dispatch on this loop.
    await asyncio.to_thread(workspace.mkdir)
    if not cl.SANDBOX_USER:
        return
    # Group-shared with the sandbox user; setgid keeps new files in the group.
    await asyncio.to_thread(os.chmod, workspace, 0o2770)
    if await _run_as_sandbox([sys.executable, "-m", "venv", ".venv"], workspace):
        raise OSError(f"could not create the session venv in {workspace}")


async def _remove_workspace(workspace: Path) -> None:
    if cl.SANDBOX_USER:
        # Files the sandbox user created (or chmod-ed) may not be deletable
        # by this user, so let their owner restore access and remove them.
        await _run_as_sandbox(
            ["sh", "-c", 'chmod -R u+rwX "$1"; rm -rf "$1"', "sh", str(workspace)],
            workspace.parent,
        )
    # Recursive delete is a blocking syscall storm on a large/full workspace;
    # off-thread for the same reason as the mkdir in _make_workspace.
    await asyncio.to_thread(shutil.rmtree, workspace, ignore_errors=True)


class Session:
    def __init__(
        self,
        session_id: str,
        owner_github_user_id: str,
        workspace: Path,
        mcp_url: str,
        mcp_headers: dict[str, str],
    ):
        self.id = session_id
        self.owner_github_user_id = owner_github_user_id
        self.token = secrets.token_urlsafe(32)
        self.workspace = workspace
        self.mcp_url = mcp_url
        self.mcp_headers = mcp_headers
        self.history: list = []
        self.api_key: str | None = None
        self.auth_token: str | None = None
        self.tools: list = []
        self.tool_defs: list[dict] = []
        self.inbox: asyncio.Queue = asyncio.Queue()
        self.subscribers: set[asyncio.Queue] = set()
        self.ready = asyncio.Event()
        self.error: str | None = None
        self.busy = False
        self.turn_task: asyncio.Task | None = None
        self.actor: asyncio.Task | None = None
        self.last_activity = time.monotonic()
        self._seq = 0
        # Test seams; the API layer never touches these.
        self.client_factory = AsyncAnthropic
        self.mcp_connect = connect_mcp
        self.file_tools = cl.make_file_tools(
            get_root=lambda: self.workspace,
            # No interactive env prompt like in the CLI: sandboxed sessions
            # get their own venv, unsandboxed ones share the service's.
            get_exec_bin=lambda: _exec_bin(self.workspace),
            on_fs_change=self._on_fs_change,
        )

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
        for queue in tuple(self.subscribers):
            # Bounded queue: a stalled SSE consumer must not grow memory for
            # the session's lifetime. SSE has no replay anyway, so the oldest
            # event is the cheapest one to drop.
            while True:
                try:
                    queue.put_nowait(event)
                    break
                except asyncio.QueueFull:
                    with contextlib.suppress(asyncio.QueueEmpty):
                        queue.get_nowait()

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=EVENT_QUEUE_SIZE)
        self.subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self.subscribers.discard(queue)

    def _on_fs_change(self, path: str) -> None:
        self.publish("fs_changed", paths=[path])

    # ----------------------------------------------------------- actor

    async def run_actor(self) -> None:
        """Own the MCP connection and consume the inbox, one turn at a time."""
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
                while True:
                    item = await self.inbox.get()
                    if item is None:
                        return
                    turn_id, content = item
                    self.turn_task = asyncio.create_task(
                        self._run_turn(turn_id, content)
                    )
                    try:
                        await self.turn_task
                    except asyncio.CancelledError:
                        # Swallow only a turn interrupt (the turn already
                        # rolled back and emitted turn_error). If the actor
                        # itself is being cancelled, the cancellation must
                        # propagate.
                        task = asyncio.current_task()
                        if task is not None and task.cancelling():
                            raise
                    finally:
                        self.turn_task = None
                        self.busy = False
        except Exception as e:  # noqa: BLE001
            # Broad by design: the session becomes unusable, record why.
            self.error = f"{type(e).__name__}: {e}"
            self.ready.set()
            # Unbrick clients: no turn will ever run again, so nothing may
            # stay queued or claim the busy slot.
            self.busy = False
            while not self.inbox.empty():
                self.inbox.get_nowait()
            self.publish("session_error", message=self.error)

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
        thinking = cl.thinking_config()
        runner = client.beta.messages.tool_runner(
            model=cl.MODEL,
            max_tokens=16000,
            system=cl.build_system_prompt(self.workspace, cl.RESULT_MAX_CHARS),
            tools=self.tools,
            messages=self.history,
            stream=True,
            cache_control={"type": "ephemeral"},
            **({"thinking": thinking} if thinking else {}),
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
            # busy flips before the terminal event so that a client reacting
            # to turn_done can immediately POST the next message without 409.
            self.busy = False
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
                message = (
                    "Your Anthropic API key was rejected. Check it or use another key."
                )
            elif "credit balance is too low" in str(error).lower():
                message = (
                    "Your Anthropic API key is out of credit. Add credit or use "
                    "another key."
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
        self.busy = False
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
        if self.turn_task is not None and not self.turn_task.done():
            self.turn_task.cancel()
            return True
        if self.busy:
            # Turn accepted but not yet dequeued by the actor: pull it back
            # out of the inbox so it never starts. The poison pill (None)
            # must survive draining — put it back.
            interrupted = False
            requeue = []
            while not self.inbox.empty():
                item = self.inbox.get_nowait()
                if item is None:
                    requeue.append(item)
                else:
                    interrupted = True
                    self.publish("turn_error", turn_id=item[0], message="interrupted")
            for item in requeue:
                self.inbox.put_nowait(item)
            if interrupted:
                self.busy = False
                return True
        return False


class SessionManager:
    def __init__(
        self,
        workspaces_root: Path | str | None = None,
        mcp_url: str | None = None,
        mcp_headers: dict[str, str] | None = None,
        mcp_connect=None,
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
        self._sse_disconnect_tasks: dict[str, asyncio.Task[None]] = {}

    async def create(self, *, owner_github_user_id: str) -> Session:
        owned = sum(
            s.owner_github_user_id == owner_github_user_id
            for s in self.sessions.values()
        )
        if owned >= MAX_SESSIONS_PER_USER:
            raise SessionLimitError
        try:
            await asyncio.to_thread(
                self.workspaces_root.mkdir, parents=True, exist_ok=True
            )
        except OSError as e:
            logger.exception("Could not create workspace root")
            raise WorkspaceStorageError from e
        session_id = uuid.uuid4().hex
        workspace = self.workspaces_root / session_id
        try:
            await _make_workspace(workspace)
        except BaseException as e:
            # Also on cancellation: to_thread's worker thread runs mkdir to
            # completion even if this await is cancelled (e.g. task killed on
            # shutdown), so the dir can land on disk with nothing left to
            # track/clean it. Nothing references `session` yet, so clean up
            # here before propagating.
            await _remove_workspace(workspace)
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

    # Reconnection cancels the short cleanup window before subscribing again.
    def open_event_stream(
        self, session: Session
    ) -> asyncio.Queue | EventStreamAlreadyActive:
        if session.subscribers:
            return EventStreamAlreadyActive()
        self._cancel_sse_disconnect(session.id)
        return session.subscribe()

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
        session.interrupt()
        if session.actor is not None and not session.actor.done():
            session.inbox.put_nowait(None)
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
        await _remove_workspace(session.workspace)

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
