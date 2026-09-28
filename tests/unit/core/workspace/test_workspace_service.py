"""Unit tests for src/core/workspace/service.py — no network, fake MCP and Anthropic."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

import anthropic
import httpx
import pytest

from src.core.workspace import client_loop, service
from src.core.workspace.service import (
    SessionManager,
    SessionStartupError,
    TurnInFlightError,
)
from tests.support.workspace_fakes import (
    FakeRunner,
    FakeStream,
    fake_client_factory,
    fake_mcp_connect,
    final_message,
    text_event,
)


def make_manager(tmp_path, mcp_connect=fake_mcp_connect):
    return SessionManager(
        workspaces_root=tmp_path / "workspaces",
        mcp_headers={},
        mcp_connect=mcp_connect,
    )


async def collect_until_done(queue, timeout=5.0):
    events = []
    while True:
        event = await asyncio.wait_for(queue.get(), timeout)
        events.append(event)
        if event["type"] in ("turn_done", "turn_error", "session_error"):
            return events


async def run_turn(session, content):
    queue = session.subscribe()
    session.submit(content)
    events = await collect_until_done(queue)
    session.unsubscribe(queue)
    return events


def test_default_connect_mcp_reuses_client_loop_bootstrap():
    """Guards against the mcp>=2.0 bootstrap being copy-pasted back into
    service.py instead of shared via client_loop.open_mcp_session."""
    assert service.connect_mcp is client_loop.open_mcp_session


def test_create_and_delete_session(tmp_path):
    async def scenario():
        manager = make_manager(tmp_path)
        session = await manager.create(owner_github_user_id="12345")
        assert session.workspace.is_dir()
        names = [t["name"] for t in session.tool_defs]
        assert "get_phase_guidance" in names
        assert "run_command" in names
        assert manager.get(session.id) is session
        assert await manager.delete(session.id)
        assert not session.workspace.exists()
        assert manager.get(session.id) is None

    asyncio.run(scenario())


def test_create_session_mcp_failure(tmp_path, caplog):
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def broken(url, headers):
        raise ConnectionError("no route to MCP")
        yield  # pragma: no cover

    async def scenario():
        manager = make_manager(tmp_path, mcp_connect=broken)
        with pytest.raises(
            SessionStartupError, match="^could not connect to MCP server$"
        ):
            await manager.create(owner_github_user_id="12345")
        assert not manager.sessions
        assert "no route to MCP" in caplog.text

    asyncio.run(scenario())


def test_create_reports_workspace_storage_error(tmp_path, monkeypatch):
    manager = make_manager(tmp_path)
    monkeypatch.setattr(service.asyncio, "to_thread", AsyncMock(side_effect=OSError))
    create_session = manager.create(owner_github_user_id="12345")
    with pytest.raises(service.WorkspaceStorageError):
        asyncio.run(create_session)
    assert manager.sessions == {}
    assert manager.get("missing") is None
    assert not manager.workspaces_root.exists()


def test_create_reports_workspace_directory_storage_error(tmp_path, monkeypatch):
    """
    Report storage failures after the workspace root has been prepared.
    """
    manager = make_manager(tmp_path)
    monkeypatch.setattr(
        service.asyncio, "to_thread", AsyncMock(side_effect=[None, OSError, None])
    )
    create_session = manager.create(owner_github_user_id="12345")
    with pytest.raises(service.WorkspaceStorageError):
        asyncio.run(create_session)
    assert manager.sessions == {}
    assert manager.get("missing") is None
    assert not manager.workspaces_root.exists()


def test_create_can_lead_to_mcp_startup_timeout(tmp_path, monkeypatch):
    # Workspaces are removed, when their MCP connection does not become ready in time.
    manager = make_manager(tmp_path)
    monkeypatch.setattr(service, "READY_TIMEOUT", 0)
    create_session = manager.create(owner_github_user_id="12345")
    with pytest.raises(SessionStartupError, match="timed out"):
        asyncio.run(create_session)
    assert manager.sessions == {}
    assert manager._sse_disconnect_tasks == {}
    # assert manager.workspaces_root.is_dir()


def test_tool_events_hide_empty_values(tmp_path):
    # UI Niceties from the backend: Empty dict tool responses are omitted (Rather just the tool name)
    session = service.Session("sid", "12345", tmp_path, "url", {})
    queue = session.subscribe()
    names = session._publish_tool_calls(
        [SimpleNamespace(type="tool_use", id="tool-1", name="guidance", input={})]
    )
    session._publish_tool_results(
        {"content": [{"type": "tool_result", "tool_use_id": "tool-1", "content": ""}]},
        names,
    )
    tool_call, tool_result = queue.get_nowait(), queue.get_nowait()
    assert names == {"tool-1": "guidance"}
    assert tool_call["data"] == {"name": "guidance"}
    assert "preview" not in tool_result["data"]


def test_stream_starts_with_thinking_started_event(tmp_path):
    session = service.Session("sid", "12345", tmp_path, "url", {})
    queue = session.subscribe()
    stream = FakeStream(
        [SimpleNamespace(type="thinking"), SimpleNamespace(type="thinking")], None
    )
    asyncio.run(session._emit_stream(stream))
    event = queue.get_nowait()
    assert event["type"] == "thinking_started"
    assert event["seq"] == 1
    assert queue.empty()


def test_interrupt_cancels_active_turn(tmp_path):
    # Interupptions stop any current API call and LLM cost to the user...
    session = service.Session("sid", "12345", tmp_path, "url", {})
    turn_task = Mock()
    turn_task.done.return_value = False
    session.turn_task = turn_task
    assert session.interrupt()
    assert turn_task.cancel.call_count == 1
    assert session.turn_task is turn_task


def test_turn_with_tool_call(tmp_path):
    from types import SimpleNamespace

    tool_use = SimpleNamespace(
        type="tool_use", id="tu_1", name="get_phase_guidance", input={"phase": "review"}
    )
    tool_response = {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": "tu_1",
                "content": [{"type": "text", "text": "[exit 0]\nguidance text"}],
            }
        ],
    }
    turns = [
        (
            FakeStream([text_event("let me check")], final_message([tool_use])),
            tool_response,
        ),
        (
            FakeStream(
                [text_event("all done")],
                final_message([SimpleNamespace(type="text", text="all done")]),
            ),
            None,
        ),
    ]

    async def scenario():
        manager = make_manager(tmp_path)
        session = await manager.create(owner_github_user_id="12345")
        session.set_key("sk-test", None)
        session.client_factory = fake_client_factory(FakeRunner(turns))
        events = await run_turn(session, "hello")
        types = [e["type"] for e in events]
        assert types[0] == "turn_started"
        assert types[-1] == "turn_done"
        assert "text_delta" in types
        assert "tool_call" in types
        assert "tool_result" in types
        assert types.count("usage") == 2
        tool_call = next(e for e in events if e["type"] == "tool_call")
        result = next(e for e in events if e["type"] == "tool_result")
        assert result["data"]["name"] == "get_phase_guidance"
        assert tool_call["data"]["args"] == {"phase": "review"}
        assert (
            result["data"]["preview"] == "[Succeeded]\nguidance text"
        )  # Succeeded replace "Exit code 2" etc (which is difficult for non-tech people to understand)
        # user, assistant(tool_use), tool_result, assistant(final)
        assert len(session.history) == 4
        assert session.busy is False
        await manager.shutdown()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("error_kind", "error_message", "expected_message"),
    [
        (
            "provider",
            "provider error",
            "Error from AI model stream. Please try again.",
        ),
        (
            "provider",
            "Your credit balance is too low to access the Anthropic API.",
            "Your Anthropic API key is out of credit. Add credit or use another key.",
        ),
        (
            "authentication",
            "invalid x-api-key",
            "Your Anthropic API key was rejected. Check it or use another key.",
        ),
    ],
)
def test_turn_api_error_rolls_back_history(
    tmp_path, caplog, error_kind, error_message, expected_message
):
    turns = [
        (
            FakeStream([text_event("hi")], final_message([])),
            None,
        )
    ]

    async def scenario():
        manager = make_manager(tmp_path)
        session = await manager.create(owner_github_user_id="12345")
        session.set_key("sk-test", None)
        request = httpx.Request("POST", "https://api.anthropic.test")
        if error_kind == "authentication":
            error = anthropic.AuthenticationError(
                error_message,
                response=httpx.Response(401, request=request),
                body=None,
            )
        else:
            error = anthropic.APIError(error_message, request, body=None)
        session.client_factory = fake_client_factory(
            FakeRunner(turns, error_at=0, error=error)
        )
        events = await run_turn(session, "hello")
        assert events[-1]["type"] == "turn_error"
        assert events[-1]["data"]["message"] == expected_message
        assert error_message in caplog.text
        assert session.history == []
        assert session.busy is False
        # The session survives a failed turn: run a working one after it.
        session.client_factory = fake_client_factory(FakeRunner(list(turns)))
        events = await run_turn(session, "again")
        assert events[-1]["type"] == "turn_done"
        assert len(session.history) == 2
        await manager.shutdown()

    asyncio.run(scenario())


def test_turn_unexpected_error_confined_to_turn(tmp_path, caplog):
    class ExplodingRunner:
        def __aiter__(self):
            async def gen():
                raise RuntimeError("unexpected bug")
                yield  # pragma: no cover

            return gen()

    async def scenario():
        manager = make_manager(tmp_path)
        session = await manager.create(owner_github_user_id="12345")
        session.set_key("sk-test", None)
        session.client_factory = fake_client_factory(ExplodingRunner())
        events = await run_turn(session, "hello")
        assert events[-1]["type"] == "turn_error"
        assert (
            events[-1]["data"]["message"] == "Workspace turn failed. Please try again."
        )
        assert "unexpected bug" in caplog.text
        assert session.history == []
        assert session.busy is False
        assert session.error is None  # session survives, actor keeps running
        assert not session.actor.done()
        await manager.shutdown()

    asyncio.run(scenario())


# Cover an interrupted provider stream without stopping the session actor.
def test_turn_cancellation_rolls_back_history(tmp_path):
    async def scenario():
        manager = make_manager(tmp_path)
        session = await manager.create(owner_github_user_id="12345")
        session.set_key("sk-test", None)
        session.client_factory = fake_client_factory(
            FakeRunner([(FakeStream([], final_message([])), None)])
        )
        session._emit_stream = AsyncMock(side_effect=asyncio.CancelledError())
        events = await run_turn(session, "hello")
        await manager.shutdown()
        return events, session.history, session.busy

    events, history, busy = asyncio.run(scenario())
    assert events[-1]["type"] == "turn_error"
    assert events[-1]["data"]["message"] == "interrupted"
    assert history == []
    assert busy is False


def test_actor_death_unbricks_session(tmp_path, caplog):
    from contextlib import asynccontextmanager

    class DyingMcp:
        async def list_tools(self):
            return SimpleNamespace(tools=[])

        async def call_tool(self, name, arguments):  # pragma: no cover
            raise AssertionError("not used")

    connections = []

    @asynccontextmanager
    async def dying_mcp_connect(url, headers):
        # Mimic the streamable-HTTP transport: a failure in its background
        # task cancels the owning task and surfaces as an error on exit.
        mcp = DyingMcp()
        mcp.die = asyncio.current_task().cancel
        connections.append(mcp)
        try:
            yield mcp
        except asyncio.CancelledError:
            raise ConnectionError("transport lost") from None

    async def scenario():
        manager = make_manager(tmp_path, mcp_connect=dying_mcp_connect)
        session = await manager.create(owner_github_user_id="12345")
        queue = session.subscribe()
        turn_started = asyncio.Event()

        async def hanging_turn(turn_id, content):
            turn_started.set()
            await asyncio.Event().wait()

        session._run_turn = hanging_turn  # type: ignore[method-assign]
        session.submit("hello")
        await turn_started.wait()
        connections[-1].die()
        await asyncio.wait_for(session.actor, timeout=5)
        await asyncio.wait({session.turn_task}, timeout=5)
        # Clients get a generic reason; the details only go to the log.
        assert session.error == "MCP connection lost"
        assert "transport lost" in caplog.text
        assert session.turn_task.cancelled()
        assert session.busy is False
        assert queue.get_nowait()["type"] == "session_error"
        await manager.shutdown()

    asyncio.run(scenario())


def test_subscriber_queue_drops_oldest_when_full(tmp_path):
    async def scenario():
        from src.core.workspace import service

        manager = make_manager(tmp_path)
        session = await manager.create(owner_github_user_id="12345")
        queue = session.subscribe()
        for i in range(service.EVENT_QUEUE_SIZE + 5):
            session.publish("text_delta", text=str(i))
        assert queue.qsize() == service.EVENT_QUEUE_SIZE
        first = queue.get_nowait()
        assert first["data"]["text"] == "5"  # oldest five dropped
        await manager.shutdown()

    asyncio.run(scenario())


def test_open_event_stream_replaces_older_stream(tmp_path):
    async def scenario():
        manager = make_manager(tmp_path)
        session = await manager.create(owner_github_user_id="12345")
        first, _ = manager.open_event_stream(session)
        second, backlog = manager.open_event_stream(session)
        # The older stream is told to end and no longer receives events.
        assert first.get_nowait() is None
        assert session.subscribers == {second}
        assert backlog == []
        manager.close_event_stream(session, first)
        assert session.id not in manager._sse_disconnect_tasks
        await manager.shutdown()

    asyncio.run(scenario())


def test_open_event_stream_replays_events_after_last_event_id(tmp_path):
    async def scenario():
        manager = make_manager(tmp_path)
        session = await manager.create(owner_github_user_id="12345")
        for n in range(3):
            session.publish("fs_changed", paths=[f"f{n}"])
        _, backlog = manager.open_event_stream(session, last_event_id=1)
        assert [e["seq"] for e in backlog] == [2, 3]
        # Up to date, unknown (e.g. from before a restart) or no id: no replay.
        assert manager.open_event_stream(session, last_event_id=3)[1] == []
        assert manager.open_event_stream(session, last_event_id=99)[1] == []
        assert manager.open_event_stream(session)[1] == []
        await manager.shutdown()

    asyncio.run(scenario())


def test_replay_buffer_is_bounded(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "EVENT_REPLAY_SIZE", 2)
    session = service.Session("sid", "12345", tmp_path, "url", {})
    for n in range(4):
        session.publish("fs_changed", paths=[f"f{n}"])
    # Events 1-2 fell out of the buffer; only what is left is replayed.
    assert [e["seq"] for e in session.events_after(0)] == [3, 4]


# Ideally this basically gives us more protection about the "Network" erros we saw.
def test_reconnect_then_61_second_timeout_deletes_session(tmp_path, monkeypatch):
    async def scenario():
        sleep = AsyncMock()
        monkeypatch.setattr(service.asyncio, "sleep", sleep)
        manager = make_manager(tmp_path)
        session = await manager.create(owner_github_user_id="12345")
        original_stream, _ = manager.open_event_stream(session)
        manager.close_event_stream(session, original_stream)
        reconnected_stream, _ = manager.open_event_stream(session)
        retained = manager.get(session.id) is session
        manager.close_event_stream(session, reconnected_stream)
        await manager._sse_disconnect_tasks[session.id]
        return (
            retained,
            sleep.await_args_list,
            manager.get(session.id),
            session.workspace.exists(),
        )

    retained, delays, expired_session, workspace_exists = asyncio.run(scenario())
    assert retained
    assert delays == [call(60)]
    assert expired_session is None
    assert not workspace_exists


# AI-Generated:
# We may change how the cleanup task works/when it happens
# Remove a delayed cleanup task after either interruption or a cleanup failure.
def test_sse_disconnect_cleanup_handles_interruption_and_failure(
    tmp_path, monkeypatch, caplog
):
    async def scenario():
        manager = make_manager(tmp_path)
        session = await manager.create(owner_github_user_id="12345")
        sleep = AsyncMock(side_effect=[asyncio.CancelledError(), None, None])
        monkeypatch.setattr(service.asyncio, "sleep", sleep)
        with pytest.raises(asyncio.CancelledError):
            await manager._delete_after_sse_60_second_timeout(session.id)
        delete = manager.delete
        failed_delete = AsyncMock(side_effect=RuntimeError("workspace unavailable"))
        manager.delete = failed_delete
        manager._sse_disconnect_tasks[session.id] = asyncio.current_task()
        await manager._delete_after_sse_60_second_timeout(session.id)
        session.subscribe()
        await manager._delete_after_sse_60_second_timeout(session.id)
        manager.delete = delete
        await manager.shutdown()
        return (
            sleep.await_count,
            failed_delete.await_args_list,
            manager._sse_disconnect_tasks,
        )

    sleep_count, delete_calls, cleanup_tasks = asyncio.run(scenario())
    assert sleep_count == 3
    assert len(delete_calls) == 1
    assert cleanup_tasks == {}
    assert "SSE reconnect cleanup failed" in caplog.text


def test_delete_publishes_session_closed(tmp_path):
    async def scenario():
        manager = make_manager(tmp_path)
        session = await manager.create(owner_github_user_id="12345")
        queue = session.subscribe()
        await manager.delete(session.id)
        events = []
        while not queue.empty():
            events.append(queue.get_nowait())
        assert events[-1]["type"] == "session_closed"
        assert not session.subscribers

    asyncio.run(scenario())


# Check idle expiry uses normal session teardown without touching active work.
def test_reap_idle_sessions(tmp_path):
    # Exercise session expiry without waiting for the production timeout.
    async def scenario():
        manager = make_manager(tmp_path)
        active = await manager.create(owner_github_user_id="12345")
        expired = await manager.create(owner_github_user_id="12345")
        expired.last_activity -= service.IDLE_SESSION_SECONDS + 1
        reaped = await manager.reap_idle_sessions()
        assert reaped == 1
        assert manager.get(active.id) is active
        assert manager.get(expired.id) is None
        await manager.shutdown()

    asyncio.run(scenario())


# AI-Generated:
# Keep the reaper running across one failed idle-session cleanup cycle.
def test_idle_reaper_logs_cleanup_failure(tmp_path, monkeypatch, caplog):
    async def scenario():
        manager = make_manager(tmp_path)
        sleep = AsyncMock(side_effect=[None, asyncio.CancelledError()])
        reap = AsyncMock(side_effect=RuntimeError("workspace unavailable"))
        monkeypatch.setattr(service.asyncio, "sleep", sleep)
        monkeypatch.setattr(manager, "reap_idle_sessions", reap)
        with pytest.raises(asyncio.CancelledError):
            await manager.run_idle_reaper()
        return sleep.await_count, reap.await_count

    sleep_count, reaper_count = asyncio.run(scenario())
    assert sleep_count == 2
    assert reaper_count == 1
    assert "workspace idle-session cleanup failed" in caplog.text
    # repeat should still be working.


def test_submit_rejects_second_turn_and_interrupt_frees_slot(tmp_path):
    async def scenario():
        session = service.Session("sid", "12345", tmp_path, "url", {})
        release = asyncio.Event()

        async def slow_turn(turn_id, content):
            await release.wait()

        session._run_turn = slow_turn  # type: ignore[method-assign]
        assert session.interrupt() is False
        session.submit("first")
        # busy from submission on, before the turn task has even started
        assert session.busy is True
        with pytest.raises(TurnInFlightError):
            session.submit("second")
        assert session.interrupt() is True
        await asyncio.wait({session.turn_task})
        assert session.busy is False
        assert session.interrupt() is False
        session.submit("third")
        release.set()
        await session.turn_task
        assert session.busy is False

    asyncio.run(scenario())


def test_fs_change_event_from_file_tool(tmp_path):
    async def scenario():
        manager = make_manager(tmp_path)
        session = await manager.create(owner_github_user_id="12345")
        queue = session.subscribe()
        write_file = next(t for t in session.file_tools if t.name == "write_file")
        out = await write_file.call({"path": "a.txt", "content": "hi"})
        assert out == "wrote 2 chars to a.txt"
        assert (session.workspace / "a.txt").read_text() == "hi"
        event = queue.get_nowait()
        assert event["type"] == "fs_changed"
        assert event["data"]["paths"] == ["a.txt"]
        await manager.shutdown()

    asyncio.run(scenario())
