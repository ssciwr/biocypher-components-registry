"""API tests for the workspace routes — TestClient over fake MCP and Anthropic."""

import time
from functools import partial
from io import BytesIO
from tempfile import NamedTemporaryFile
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.dependencies import get_current_auth_session
from src.api.routers import workspace as workspace_router
from src.core.auth.models import AuthSession
from src.core.workspace.service import SessionManager
from tests.support.workspace_fakes import (
    FakeRunner,
    FakeStream,
    fake_client_factory,
    fake_mcp_connect,
    final_message,
    text_event,
)

PREFIX = "/agent/api/v1"


@pytest.fixture
def manager(tmp_path, monkeypatch):
    monkeypatch.setattr("src.api.app.agentic_api_active", True)
    return SessionManager(
        workspaces_root=tmp_path / "workspaces",
        mcp_headers={},
        mcp_connect=fake_mcp_connect,
    )


@pytest.fixture
def auth_session():
    return AuthSession(github_user_id="12345")


@pytest.fixture
def client(manager, auth_session):
    app = create_app(workspace_manager=manager)
    app.dependency_overrides[get_current_auth_session] = lambda: auth_session
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def session(client, manager):
    """A created session: (session_id, auth headers, Session object)."""
    created = client.post(f"{PREFIX}/sessions").json()
    headers = {"Authorization": f"Bearer {created['session_token']}"}
    return created["session_id"], headers, manager.get(created["session_id"])


def wait_not_busy(client, sid, headers, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = client.get(f"{PREFIX}/sessions/{sid}", headers=headers).json()
        if not state["busy"]:
            return state
        time.sleep(0.02)
    raise AssertionError("turn did not finish in time")


# ------------------------------------------------------------- lifecycle


def test_create_session_returns_tools_and_token(client):
    response = client.post(f"{PREFIX}/sessions")
    assert response.status_code == 201
    body = response.json()
    assert body["session_id"]
    assert body["session_token"]
    names = [t["name"] for t in body["tools"]]
    assert "get_phase_guidance" in names
    assert "write_file" in names


def test_create_session_requires_github_auth(manager):
    # Ensure authentication is required
    with TestClient(create_app(workspace_manager=manager)) as anonymous:
        response = anonymous.post(f"{PREFIX}/sessions")
    assert response.status_code == 401
    assert response.json()["detail"] == "GitHub sign-in required."
    assert manager.sessions == {}


def test_session_routes_require_same_github_user(client):
    """
    Reject valid workspace tokens presented by another GitHub user.
    """
    created = client.post(f"{PREFIX}/sessions").json()
    headers = {"Authorization": f"Bearer {created['session_token']}"}
    same_user = client.get(
        f"{PREFIX}/sessions/{created['session_id']}", headers=headers
    )
    client.app.dependency_overrides[get_current_auth_session] = lambda: AuthSession(
        github_user_id="67890"
    )
    # Another user cannot access the first user ("same_user")s session information
    other_user = client.get(
        f"{PREFIX}/sessions/{created['session_id']}", headers=headers
    )
    no_token = client.get(f"{PREFIX}/sessions/{created['session_id']}")
    assert same_user.status_code == 200
    assert other_user.status_code == 401
    assert no_token.status_code == 401


def test_auth_required_and_checked(client, session):
    sid, headers, _ = session
    assert client.get(f"{PREFIX}/sessions/{sid}").status_code == 401
    bad = {"Authorization": "Bearer wrong-token"}
    assert client.get(f"{PREFIX}/sessions/{sid}", headers=bad).status_code == 401
    assert client.get(f"{PREFIX}/sessions/{sid}", headers=headers).status_code == 200
    # unknown session id gives the same 401, not a distinguishable 404
    assert client.get(f"{PREFIX}/sessions/nope", headers=headers).status_code == 401


def test_delete_session(client, manager, session):
    sid, headers, session_obj = session
    workspace = session_obj.workspace
    assert client.delete(f"{PREFIX}/sessions/{sid}", headers=headers).status_code == 204
    assert manager.get(sid) is None
    assert not workspace.exists()
    assert client.get(f"{PREFIX}/sessions/{sid}", headers=headers).status_code == 401


# ------------------------------------------------------------ key + chat


def test_message_requires_key_then_runs(client, session):
    sid, headers, session_obj = session
    url = f"{PREFIX}/sessions/{sid}/messages"
    assert client.post(url, headers=headers, json={"content": "hi"}).status_code == 428

    assert (
        client.post(
            f"{PREFIX}/sessions/{sid}/key", headers=headers, json={}
        ).status_code
        == 400
    )
    response = client.post(
        f"{PREFIX}/sessions/{sid}/key", headers=headers, json={"api_key": "sk-test"}
    )
    assert response.status_code == 204
    assert client.get(f"{PREFIX}/sessions/{sid}", headers=headers).json()["has_key"]

    turns = [
        (
            FakeStream(
                [text_event("hello back")],
                final_message([SimpleNamespace(type="text", text="hello back")]),
            ),
            None,
        )
    ]
    session_obj.client_factory = fake_client_factory(FakeRunner(turns))
    response = client.post(url, headers=headers, json={"content": "hi"})
    assert response.status_code == 202
    assert response.json()["turn_id"]
    wait_not_busy(client, sid, headers)
    assert len(session_obj.history) == 2

    assert client.post(url, headers=headers, json={"content": ""}).status_code == 400


def test_message_conflict_while_busy(client, session):
    sid, headers, session_obj = session
    session_obj.set_key("sk-test", None)
    session_obj.busy = True
    response = client.post(
        f"{PREFIX}/sessions/{sid}/messages", headers=headers, json={"content": "hi"}
    )
    assert response.status_code == 409
    session_obj.busy = False


def test_interrupt_without_turn(client, session):
    sid, headers, _ = session
    response = client.post(f"{PREFIX}/sessions/{sid}/interrupt", headers=headers)
    assert response.status_code == 409


def test_events_stream_snapshot_and_token_query(manager):
    # TestClient cannot cancel an infinite SSE response, so this test runs a
    # real uvicorn server in a thread and closes a real TCP connection.
    import socket
    import threading
    import time as time_mod

    import httpx
    import uvicorn

    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()

    app = create_app(workspace_manager=manager)
    app.dependency_overrides[get_current_auth_session] = lambda: AuthSession(
        github_user_id="12345"
    )
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time_mod.monotonic() + 10
        while not server.started:
            assert time_mod.monotonic() < deadline, "uvicorn did not start"
            time_mod.sleep(0.02)
        base = f"http://127.0.0.1:{port}{PREFIX}"
        created = httpx.post(f"{base}/sessions", timeout=10).json()
        url = f"{base}/sessions/{created['session_id']}/events"
        lines = []
        with httpx.stream(
            "GET", url, params={"token": created["session_token"]}, timeout=10
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            second_stream = httpx.get(
                url, params={"token": created["session_token"]}, timeout=10
            )
            assert second_stream.status_code == 409
            for line in response.iter_lines():
                lines.append(line)
                if len(lines) >= 2:
                    break
        assert lines[0] == "event: session_state"
        assert '"has_key": false' in lines[1]
        assert manager.get(created["session_id"]) is not None
        deleted = httpx.delete(
            f"{base}/sessions/{created['session_id']}",
            params={"token": created["session_token"]},
            timeout=10,
        )
        assert deleted.status_code == 204
        assert manager.get(created["session_id"]) is None
    finally:
        server.should_exit = True
        thread.join(timeout=10)


# ----------------------------------------------------------------- files
# These three tests below are AI-generated and then reviewed.
# I requested each one based on missing lines(and specific exceptions being thrown) in the Codecov report.
#
def test_download_archives_workspace_files_without_symlinks(client, session):
    sid, headers, session_obj = session
    (session_obj.workspace / "adapter.py").write_text("print('adapter')")
    (session_obj.workspace / "linked.py").symlink_to(
        session_obj.workspace / "adapter.py"
    )
    response = client.get(f"{PREFIX}/sessions/{sid}/download", headers=headers)
    with ZipFile(BytesIO(response.content)) as archive:
        names = archive.namelist()
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert names == ["adapter.py"]


def test_workspace_archive_removes_temp_file_when_writing_fails(tmp_path, monkeypatch):
    archive_root = tmp_path / "archives"
    archive_root.mkdir()
    archive = MagicMock()
    archive.__enter__.return_value.write.side_effect = OSError
    monkeypatch.setattr(
        workspace_router,
        "NamedTemporaryFile",
        partial(NamedTemporaryFile, dir=archive_root),
    )
    monkeypatch.setattr(workspace_router, "ZipFile", Mock(return_value=archive))
    with pytest.raises(OSError):
        workspace_router._create_workspace_archive(tmp_path)
    assert archive.__enter__.return_value.write.call_count == 1
    assert list(archive_root.iterdir()) == []
    assert archive.__exit__.called


def test_download_returns_conflict_when_archive_creation_fails(
    client, session, monkeypatch
):
    sid, headers, _ = session
    create_archive = Mock(side_effect=OSError)
    monkeypatch.setattr(workspace_router, "_create_workspace_archive", create_archive)
    response = client.get(f"{PREFIX}/sessions/{sid}/download", headers=headers)
    assert response.status_code == 409
    assert response.json() == {"detail": "Could not prepare workspace download."}
    assert create_archive.call_count == 1


def test_file_path_confinement(client, session):
    sid, headers, _ = session
    for path in ("../escape.txt", "/etc/passwd"):
        response = client.get(
            f"{PREFIX}/sessions/{sid}/file", params={"path": path}, headers=headers
        )
        assert response.status_code == 400, path
