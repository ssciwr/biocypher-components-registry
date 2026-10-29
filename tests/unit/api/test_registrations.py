"""HTTP contracts for synchronous registration and automatic pre-flight."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from src.api.app import create_app
from src.api.dependencies import get_optional_auth_session, get_registration_store
from src.api.schemas.registrations import REGISTRATION_CREATE_EXAMPLE
from src.core.auth.models import AuthSession
from src.core.registration.service import submit_registration
from src.core.shared.errors import RepositoryUnavailableError
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore
from src.persistence.tables import (
    registration_events_table,
    registration_sources_table,
    registry_entries_table,
)
from tests.support.croissant_fixtures import sample_adapter_document


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    path = tmp_path / "adapter"
    path.mkdir()
    (path / "croissant.jsonld").write_text(json.dumps(sample_adapter_document()))
    return path


@pytest.fixture
def store(tmp_path: Path) -> SQLiteRegistrationStore:
    return SQLiteRegistrationStore(tmp_path / "registry.sqlite3")


@pytest.fixture
def client(store) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_registration_store] = lambda: store
    app.dependency_overrides[get_optional_auth_session] = lambda: AuthSession(
        github_user_id="12345"
    )
    return TestClient(app)


def assert_no_registration_writes(store):
    with store.engine.connect() as connection:
        for table in (
            registration_sources_table,
            registry_entries_table,
            registration_events_table,
        ):
            assert connection.scalar(select(func.count()).select_from(table)) == 0


def test_registration_create_openapi_example_is_available():
    schema = create_app().openapi()
    assert (
        schema["components"]["schemas"]["RegistrationCreateRequest"]["example"]
        == REGISTRATION_CREATE_EXAMPLE
    )


def test_create_registration_endpoint_persists_accepted_registration(
    client, repository, store
):
    response = client.post(
        "/api/v1/registrations",
        json={
            "repository_location": str(repository),
            "license_value": "MIT",
            "doi": "10.5281/zenodo.1234567",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["attempt_status"] == "SUCCEEDED"
    assert payload["adapter_name"] == "Example Adapter"
    assert payload["adapter_id"] == "example-adapter"
    assert payload["published_version"] == "1.0.0"
    assert payload["validation_details"] == []
    stored = store.get_registration(payload["registration_id"])
    assert stored.status == "VALID"
    assert stored.license_value == "MIT"
    assert stored.doi == "10.5281/zenodo.1234567"
    assert stored.submitted_by_github_user_id == "12345"
    assert [
        event.event_type
        for event in store.list_registration_events(stored.registration_id)
    ] == ["VALID_CREATED"]


@pytest.mark.parametrize(
    "content, reason",
    [
        ("{", "INVALID_JSON"),
        ("[]", "INVALID_JSON"),
        ("{}", "SCHEMA_INVALID"),
        (None, "METADATA_NOT_FOUND"),
    ],
)
def test_failed_first_registration_returns_errors_without_records(
    client, repository, store, content, reason
):
    path = repository / "croissant.jsonld"
    if content is None:
        path.unlink()
    else:
        path.write_text(content)
    response = client.post(
        "/api/v1/registrations", json={"repository_location": str(repository)}
    )
    assert response.status_code == 200
    assert response.json()["attempt_status"] == "FAILED"
    assert response.json()["reason_code"] == reason
    assert response.json()["registration_id"] is None
    assert response.json()["published_version"] is None
    if reason == "INVALID_JSON":
        if content == "{":
            detail = response.json()["validation_details"][0]
            assert (detail["line"], detail["column"]) == (1, 2)
            assert detail["source_file"] == "croissant.jsonld"
            assert detail["location_kind"] == "value"
        else:
            assert response.json()["validation_details"] == []
    assert_no_registration_writes(store)


def test_retry_repeats_initial_request_with_same_version(client, repository, store):
    path = repository / "croissant.jsonld"
    path.write_text("{")
    assert (
        client.post(
            "/api/v1/registrations", json={"repository_location": str(repository)}
        ).json()["attempt_status"]
        == "FAILED"
    )
    assert_no_registration_writes(store)
    path.write_text(json.dumps(sample_adapter_document()))
    response = client.post(
        "/api/v1/registrations", json={"repository_location": str(repository)}
    )
    assert response.status_code == 201
    assert response.json()["published_version"] == "1.0.0"


def test_failed_registration_returns_schema_context_without_database_writes(
    client, repository, store
):
    metadata = sample_adapter_document()
    metadata.pop("keywords")
    metadata.pop("license")
    (repository / "croissant.jsonld").write_text(
        "\n\n" + json.dumps(metadata, indent=2)
    )
    response = client.post(
        "/api/v1/registrations", json={"repository_location": str(repository)}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["attempt_status"] == "FAILED"
    assert payload["registration_id"] is None
    assert payload["reason_code"] == "SCHEMA_INVALID"
    assert payload["message"] == payload["validation_errors"][0]
    assert [detail["message"] for detail in payload["validation_details"]] == payload[
        "validation_errors"
    ]
    details = {detail["json_path"]: detail for detail in payload["validation_details"]}
    assert details["$.keywords"]["requirement"] == "Required property"
    assert (
        details["$.keywords"]["expected_format"]
        == "An array containing at least one non-empty string"
    )
    assert details["$.license"]["expected_format"] == "A non-empty string"
    assert details["$.keywords"]["line"] == 3
    assert details["$.keywords"]["column"] == 1
    assert details["$.keywords"]["location_kind"] == "containing_object"
    assert details["$.keywords"]["source_file"] == "croissant.jsonld"
    assert "top-level object" in details["$.keywords"]["location_description"]
    assert_no_registration_writes(store)


def test_duplicate_repository_returns_conflict(client, repository, store):
    first = client.post(
        "/api/v1/registrations", json={"repository_location": str(repository)}
    ).json()
    response = client.post(
        "/api/v1/registrations", json={"repository_location": str(repository)}
    )
    assert response.status_code == 409
    assert "already registered" in response.json()["detail"]
    assert len(store.list_registration_events(first["registration_id"])) == 1


def test_missing_local_path_is_a_request_error(client, tmp_path, store):
    response = client.post(
        "/api/v1/registrations", json={"repository_location": str(tmp_path / "absent")}
    )
    assert response.status_code == 400
    assert_no_registration_writes(store)


def test_detail_and_list_expose_accepted_registration(client, repository):
    created = client.post(
        "/api/v1/registrations", json={"repository_location": str(repository)}
    ).json()
    detail = client.get(f"/api/v1/registrations/{created['registration_id']}").json()
    assert detail["status"] == "VALID"
    assert detail["metadata"]["version"] == "1.0.0"
    items = client.get("/api/v1/registrations").json()["items"]
    assert len(items) == 1
    assert items[0]["status"] == "VALID"
    assert "metadata" not in items[0]
    assert "validation_errors" not in items[0]


def test_empty_registration_list(client):
    assert client.get("/api/v1/registrations").json() == {"items": []}


@pytest.mark.parametrize(
    "suffix, method",
    [("", "get"), ("/events", "get"), ("/process", "post"), ("/revalidate", "post")],
)
def test_unknown_registration_returns_not_found(client, suffix, method):
    assert (
        getattr(client, method)(f"/api/v1/registrations/missing{suffix}").status_code
        == 404
    )


@pytest.mark.parametrize("present, expected", [(True, "FOUND"), (False, "NOT_FOUND")])
def test_presence_check_normalizes_branch_links(monkeypatch, present, expected):
    exists = Mock(return_value=present)
    monkeypatch.setattr("src.api.routers.registrations.remote_metadata_exists", exists)
    response = TestClient(create_app()).get(
        "/api/v1/registrations/croissant-file-present-check",
        params={
            "repository_url": "https://gitlab.example.org/group/subgroup/repo/-/blob/develop/croissant.jsonld",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == expected
    assert response.json()["has_croissant_file"] is present
    exists.assert_called_once_with("https://gitlab.example.org/group/subgroup/repo")


def test_inaccessible_repository_is_unavailable_not_missing(monkeypatch):
    monkeypatch.setattr(
        "src.api.routers.registrations.remote_metadata_exists",
        Mock(side_effect=RepositoryUnavailableError("Access restricted.")),
    )
    response = TestClient(create_app()).get(
        "/api/v1/registrations/croissant-file-present-check",
        params={"repository_url": "https://github.com/org/repo"},
    )
    assert response.json()["status"] == "UNAVAILABLE"
    assert response.json()["reason_code"] == "REPOSITORY_UNAVAILABLE"


def test_invalid_presence_url_is_unavailable():
    response = TestClient(create_app()).get(
        "/api/v1/registrations/croissant-file-present-check",
        params={"repository_url": "not-a-url"},
    )
    assert response.json()["status"] == "UNAVAILABLE"
    assert response.json()["reason_code"] == "INVALID_REPOSITORY_URL"


def test_legacy_process_endpoint_can_process_staged_sources(client, repository, store):
    staged = submit_registration(str(repository), store)
    response = client.post(f"/api/v1/registrations/{staged.registration_id}/process")
    assert response.status_code == 200
    assert response.json()["status"] == "VALID"


def test_legacy_processing_cannot_bypass_update_ownership(client, repository, store):
    staged = submit_registration(
        str(repository), store, submitted_by_github_user_id="another-account"
    )
    for action in ("process", "revalidate"):
        response = client.post(
            f"/api/v1/registrations/{staged.registration_id}/{action}"
        )
        assert response.status_code == 403
    assert [
        event.event_type
        for event in store.list_registration_events(staged.registration_id)
    ] == ["SUBMITTED"]


def test_success_event_is_available_from_history(client, repository):
    created = client.post(
        "/api/v1/registrations", json={"repository_location": str(repository)}
    ).json()
    events = client.get(
        f"/api/v1/registrations/{created['registration_id']}/events"
    ).json()["items"]
    assert [event["event_type"] for event in events] == ["VALID_CREATED"]


def test_registration_openapi_documents_success_and_unsuccessful_attempts():
    responses = create_app().openapi()["paths"]["/api/v1/registrations"]["post"][
        "responses"
    ]
    assert "200" in responses
    assert "201" in responses
    assert "409" in responses
    assert (
        responses["200"]["content"]["application/json"]["schema"]
        == responses["201"]["content"]["application/json"]["schema"]
    )


def stream_events(response):
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-accel-buffering"] == "no"
    return [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]


def test_stream_registration_reports_success_only_after_acceptance(
    client, repository, store
):
    events = stream_events(
        client.post(
            "/api/v1/registrations/stream",
            json={"repository_location": str(repository)},
        )
    )
    assert events[0]["type"] == "snapshot"
    assert all(check["status"] == "PENDING" for check in events[0]["checks"])
    assert events[-1]["type"] == "result"
    result = events[-1]["result"]
    assert result["attempt_status"] == "SUCCEEDED"
    assert result["profile_version"] == "v1"
    assert all(check["status"] == "PASSED" for check in result["validation_checks"])
    assert store.get_registration(result["registration_id"]).status == "VALID"
    states = [
        (event["check"]["id"], event["check"]["status"])
        for event in events
        if event["type"] == "check"
    ]
    assert ("file", "RUNNING") in states
    assert ("schema", "PASSED") in states
    assert ("dataset:0", "PASSED") in states


def test_stream_schema_failure_preserves_diagnostics_and_no_writes(
    client, repository, store
):
    document = sample_adapter_document()
    document.pop("keywords")
    (repository / "croissant.jsonld").write_text(json.dumps(document, indent=2))
    events = stream_events(
        client.post(
            "/api/v1/registrations/stream",
            json={"repository_location": str(repository)},
        )
    )
    result = events[-1]["result"]
    assert result["attempt_status"] == "FAILED"
    reports = {check["id"]: check for check in result["validation_checks"]}
    assert reports["file"]["status"] == "PASSED"
    assert reports["schema"]["status"] == "FAILED"
    assert reports["semantics"]["status"] == "PASSED"
    detail = reports["schema"]["validation_details"][0]
    assert detail["message"] == "'keywords' is a required property"
    assert detail["json_path"] == "$.keywords"
    assert detail["location_kind"] == "containing_object"
    assert detail["line"] == 1
    assert_no_registration_writes(store)


def test_stream_invalid_json_blocks_validation_without_claiming_a_schema(
    client, repository, store
):
    (repository / "croissant.jsonld").write_text("{")
    events = stream_events(
        client.post(
            "/api/v1/registrations/stream",
            json={"repository_location": str(repository)},
        )
    )
    result = events[-1]["result"]
    assert result["reason_code"] == "INVALID_JSON"
    file, *blocked = result["validation_checks"]
    assert file["status"] == "FAILED"
    assert file["validation_details"][0]["line"] == 1
    assert all(check["status"] == "NOT_RUN" and check["reason"] for check in blocked)
    assert all(check["profile_version"] is None for check in blocked)
    assert_no_registration_writes(store)


def test_stream_duplicate_request_returns_terminal_error_without_resubmission(
    client, repository, store
):
    client.post("/api/v1/registrations", json={"repository_location": str(repository)})
    events = stream_events(
        client.post(
            "/api/v1/registrations/stream",
            json={"repository_location": str(repository)},
        )
    )
    assert events[-1]["type"] == "error"
    assert events[-1]["status_code"] == 409
    assert not any(event["type"] == "result" for event in events)
    assert len(store.list_active_registrations()) == 1


def test_schema_endpoint_returns_deployed_schema_and_rejects_unknown_versions(client):
    from src.core.schema.profile import load_schema

    response = client.get("/api/v1/schemas/v1")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/schema+json"
    assert response.json() == load_schema("v1")
    assert client.get("/api/v1/schemas/unknown").status_code == 404


def test_stream_openapi_documents_event_envelope():
    schema = create_app().openapi()
    content = schema["paths"]["/api/v1/registrations/stream"]["post"]["responses"][
        "200"
    ]["content"]
    assert content["text/event-stream"]["schema"]["$ref"].endswith(
        "/RegistrationStreamEvent"
    )


def test_live_progress_and_heartbeats_arrive_before_processing_finishes(
    repository, store, monkeypatch
):
    import asyncio
    import threading

    from src.api.routers import registrations as router
    from src.api.schemas.registrations import RegistrationCreateRequest
    from src.core.registration import service

    release = threading.Event()
    discover = service._discover_registration_metadata

    def blocked_discovery(request):
        if not release.wait(5):
            raise RuntimeError("Test did not release discovery")
        return discover(request)

    monkeypatch.setattr(service, "_discover_registration_metadata", blocked_discovery)
    monkeypatch.setattr(router, "HEARTBEAT_SECONDS", 0.02)

    async def exercise():
        stream = router._registration_events(
            RegistrationCreateRequest(repository_location=str(repository)), store, None
        )
        try:
            assert "event: snapshot" in await anext(stream)
            update = await asyncio.wait_for(anext(stream), 2)
            assert '"id":"file"' in update
            assert '"status":"RUNNING"' in update
            assert not release.is_set()
            assert await asyncio.wait_for(anext(stream), 2) == ": heartbeat\n\n"
            release.set()
            remaining = [event async for event in stream]
            assert "event: result" in remaining[-1]
        finally:
            release.set()
            await stream.aclose()

    asyncio.run(exercise())


def test_disconnect_keeps_one_processing_attempt_without_saving_failed_records(
    repository, store, monkeypatch
):
    import asyncio
    import threading

    from src.api.routers import registrations as router
    from src.api.schemas.registrations import RegistrationCreateRequest
    from src.core.registration import service

    release = threading.Event()
    calls = []
    discover = service._discover_registration_metadata
    (repository / "croissant.jsonld").write_text("{")

    def blocked_discovery(request):
        calls.append(request)
        if not release.wait(5):
            raise RuntimeError("Test did not release discovery")
        return discover(request)

    monkeypatch.setattr(service, "_discover_registration_metadata", blocked_discovery)

    async def exercise():
        stream = router._registration_events(
            RegistrationCreateRequest(repository_location=str(repository)), store, None
        )
        try:
            await anext(stream)
            await asyncio.wait_for(anext(stream), 2)
            await stream.aclose()
        finally:
            release.set()
            await asyncio.gather(*list(router._processing_tasks))

    asyncio.run(exercise())
    assert len(calls) == 1
    assert_no_registration_writes(store)


def test_persistence_failure_does_not_turn_passed_validation_checks_red(
    client, repository, store, monkeypatch
):
    def cannot_save(*args, **kwargs):
        raise OSError("Storage unavailable")

    monkeypatch.setattr(store, "accept_candidate", cannot_save)
    events = stream_events(
        client.post(
            "/api/v1/registrations/stream",
            json={"repository_location": str(repository)},
        )
    )
    result = events[-1]["result"]
    assert result["attempt_status"] == "FAILED"
    assert all(check["status"] == "PASSED" for check in result["validation_checks"])
    assert result["message"] == "Storage unavailable"
    assert_no_registration_writes(store)


def test_progress_is_flushed_over_http_before_discovery_finishes(
    client, repository, monkeypatch
):
    import socket
    import threading
    import time

    import httpx
    import uvicorn

    from src.core.registration import service

    release = threading.Event()
    discover = service._discover_registration_metadata

    def blocked_discovery(request):
        if not release.wait(5):
            raise RuntimeError("Test did not release discovery")
        return discover(request)

    monkeypatch.setattr(service, "_discover_registration_metadata", blocked_discovery)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    server = uvicorn.Server(
        uvicorn.Config(client.app, lifespan="off", log_level="warning")
    )
    thread = threading.Thread(
        target=server.run, kwargs={"sockets": [listener]}, daemon=True
    )
    thread.start()
    try:
        deadline = time.monotonic() + 3
        while not server.started:
            assert thread.is_alive()
            assert time.monotonic() < deadline
            time.sleep(0.01)
        with (
            httpx.Client(timeout=3, trust_env=False) as transport,
            transport.stream(
                "POST",
                f"http://127.0.0.1:{listener.getsockname()[1]}/api/v1/registrations/stream",
                json={"repository_location": str(repository)},
            ) as response,
        ):
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-store"
            events = iter(response.iter_lines())
            first = next(line for line in events if line.startswith("data: "))
            assert json.loads(first.removeprefix("data: "))["type"] == "snapshot"
            running = next(line for line in events if line.startswith("data: "))
            check = json.loads(running.removeprefix("data: "))["check"]
            assert (check["id"], check["status"]) == ("file", "RUNNING")
            assert not release.is_set()
            release.set()
            remaining = [
                json.loads(line.removeprefix("data: "))
                for line in events
                if line.startswith("data: ")
            ]
            assert remaining[-1]["type"] == "result"
            assert remaining[-1]["result"]["attempt_status"] == "SUCCEEDED"
    finally:
        release.set()
        server.should_exit = True
        thread.join(timeout=5)
        listener.close()
    assert not thread.is_alive()
