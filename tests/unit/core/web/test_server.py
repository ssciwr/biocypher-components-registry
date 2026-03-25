from __future__ import annotations

import io
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.core.registration.models import BatchRefreshSummary
from src.core.registration.service import submit_registration
from src.persistence.registration_sqlite_store import SQLiteRegistrationStore
from src.core.web import server as web_ui_new


def _valid_adapter_document() -> dict[str, Any]:
    return {
        "@context": {
            "@language": "en",
            "@vocab": "https://schema.org/",
            "sc": "https://schema.org/",
            "cr": "http://mlcommons.org/croissant/",
            "dct": "http://purl.org/dc/terms/",
            "conformsTo": "dct:conformsTo",
            "recordSet": "cr:recordSet",
            "field": "cr:field",
            "source": "cr:source",
            "fileObject": "cr:fileObject",
            "extract": "cr:extract",
            "column": "cr:column",
            "dataType": {"@id": "cr:dataType", "@type": "@vocab"},
            "examples": {"@id": "cr:examples", "@type": "@json"},
            "citeAs": "cr:citeAs",
        },
        "@type": "SoftwareSourceCode",
        "@id": "example-adapter",
        "name": "Example Adapter",
        "description": "Adapter description",
        "dct:conformsTo": "https://bioschemas.org/profiles/ComputationalTool/1.0-RELEASE/",
        "version": "1.0.0",
        "license": "https://opensource.org/licenses/MIT",
        "codeRepository": "https://example.org/repo",
        "programmingLanguage": "Python",
        "targetProduct": "BioCypher",
        "creator": [{"@type": "Person", "name": "Example Creator"}],
        "keywords": ["adapter"],
        "hasPart": [
            {
                "@type": "sc:Dataset",
                "name": "Example dataset",
                "description": "Example dataset",
                "dct:conformsTo": "http://mlcommons.org/croissant/1.0",
                "citeAs": "https://example.org/dataset",
                "creator": [{"@type": "Person", "name": "Example Creator"}],
                "datePublished": "2024-01-01T00:00:00",
                "license": "https://opensource.org/licenses/MIT",
                "url": "https://example.org/dataset",
                "version": "1.0.0",
                "distribution": [
                    {
                        "@id": "file-1",
                        "@type": "cr:FileObject",
                        "name": "data.csv",
                        "contentUrl": "data.csv",
                        "encodingFormat": "text/csv",
                        "sha256": "abc123",
                    }
                ],
                "recordSet": [
                    {
                        "@id": "rs-1",
                        "@type": "cr:RecordSet",
                        "name": "records",
                        "field": [
                            {
                                "@id": "rs-1/id",
                                "@type": "cr:Field",
                                "name": "id",
                                "description": "Column id",
                                "dataType": "cr:Int64",
                                "source": {
                                    "fileObject": {"@id": "file-1"},
                                    "extract": {"column": "id"},
                                },
                            }
                        ],
                    }
                ],
            }
        ],
    }


def _invalid_adapter_document() -> dict[str, Any]:
    document = _valid_adapter_document()
    document.pop("version")
    return document


def test_build_request_from_form_supports_existing_and_generated_datasets() -> None:
    request = web_ui_new._build_request_from_form(
        {
            "output": "adapter.jsonld",
            "name": "Example Adapter",
            "description": "Adapter description",
            "version": "1.0.0",
            "license": "MIT",
            "code_repository": "https://example.org/repo",
            "validate": "true",
            "dataset_generator": "auto",
            "creators_data": json.dumps(
                [
                    {
                        "name": "Alice",
                        "affiliation": "Example Lab",
                        "identifier": "https://orcid.org/0000-0000-0000-0001",
                    }
                ]
            ),
            "keywords": "adapter,biocypher",
            "datasets_data": json.dumps(
                [
                    {
                        "name": "Existing",
                        "description": "Existing dataset",
                        "version": "",
                        "license": "",
                        "url": "",
                        "uiMode": "existing",
                        "uiExistingPath": "/tmp/dataset.jsonld",
                    },
                    {
                        "name": "Networks",
                        "description": "Network interactions",
                        "version": "1.0.0",
                        "license": "MIT",
                        "url": "https://omnipathdb.org/",
                        "datePublished": "2016-06-01",
                        "citeAs": "https://omnipathdb.org/",
                        "uiMode": "generate",
                        "uiInputPath": "data/in/sample_networks_omnipath.tsv",
                        "uiCreators": ["Saezlab,,https://www.saezlab.com/"],
                    },
                ]
            ),
        }
    )

    assert request.dataset_generator == "auto"
    assert request.dataset_paths == ["/tmp/dataset.jsonld"]
    assert len(request.generated_datasets) == 1
    assert request.generated_datasets[0].name == "Networks"


def test_format_event_errors_returns_newline_joined_json_list() -> None:
    formatted = web_ui_new._format_event_errors(
        json.dumps(["first problem", "second problem"])
    )

    assert formatted == "first problem\nsecond problem"


def test_format_event_errors_returns_raw_string_for_non_json_input() -> None:
    formatted = web_ui_new._format_event_errors("plain text error")

    assert formatted == "plain text error"


def test_build_request_from_form_writes_manual_legacy_dataset(tmp_path: Path) -> None:
    request = web_ui_new._build_request_from_form(
        {
            "output": "adapter.jsonld",
            "name": "Example Adapter",
            "description": "Adapter description",
            "version": "1.0.0",
            "license": "MIT",
            "code_repository": "https://example.org/repo",
            "validate": "true",
            "dataset_generator": "auto",
            "creators_data": json.dumps(
                [
                    {
                        "name": "Alice",
                        "affiliation": "Example Lab",
                        "identifier": "https://orcid.org/0000-0000-0000-0001",
                    }
                ]
            ),
            "keywords": "adapter,biocypher",
            "datasets_data": json.dumps(
                [
                    {
                        "name": "Networks",
                        "description": "Network interactions",
                        "version": "1.0.0",
                        "license": "MIT",
                        "url": "https://omnipathdb.org/",
                        "datePublished": "2016-06-01",
                        "citeAs": "https://omnipathdb.org/",
                    }
                ]
            )
        },
        output_dir=tmp_path,
    )

    assert len(request.dataset_paths) == 1
    assert Path(request.dataset_paths[0]).exists()
    assert request.generated_datasets == []


def test_state_from_adapter_config_normalizes_current_config_schema() -> None:
    state = web_ui_new._state_from_adapter_config(
        {
            "dataset_generator": "auto",
            "validate": True,
            "adapter": {
                "output": "adapter.jsonld",
                "name": "Example Adapter",
                "description": "Adapter description",
                "version": "1.0.0",
                "license": "MIT",
                "code_repository": "https://example.org/repo",
                "adapter_id": "example-adapter",
                "keywords": ["adapter", "biocypher"],
                "creators": [
                    {
                        "name": "Alice",
                        "affiliation": "Example Lab",
                        "identifier": "https://orcid.org/0000-0000-0000-0001",
                    }
                ],
            },
            "datasets": [
                {"mode": "existing", "path": "/tmp/dataset.jsonld"},
                {
                    "mode": "generate",
                    "input": "data/in/sample_intercell.tsv",
                    "name": "Intercell",
                    "description": "Intercell roles",
                    "license": "MIT",
                    "url": "https://omnipathdb.org/",
                    "dataset_version": "1.0.0",
                    "date_published": "2016-06-05",
                    "citation": "https://omnipathdb.org/",
                    "creators": [{"name": "Saezlab", "url": "https://www.saezlab.com/"}],
                },
            ],
        }
    )

    assert state["dataset_generator"] == "auto"
    assert state["validate"] is True
    assert state["name"] == "Example Adapter"
    assert len(state["datasets"]) == 2
    assert state["datasets"][0]["uiMode"] == "existing"
    assert state["datasets"][0]["uiExistingPath"] == "/tmp/dataset.jsonld"
    assert state["datasets"][1]["uiMode"] == "generate"
    assert state["datasets"][1]["uiInputPath"] == "data/in/sample_intercell.tsv"


def test_state_from_adapter_config_keeps_preloaded_dataset_details() -> None:
    state = web_ui_new._state_from_adapter_config(
        {
            "adapter": {
                "name": "Example Adapter",
                "description": "Adapter description",
                "version": "1.0.0",
                "license": "MIT",
                "code_repository": "https://example.org/repo",
                "keywords": ["adapter"],
                "creators": [{"name": "Alice"}],
            },
            "datasets": [
                {
                    "mode": "generate",
                    "input": "data/in/sample_intercell.tsv",
                    "name": "Intercell",
                    "description": "Intercell roles",
                    "license": "MIT",
                    "url": "https://omnipathdb.org/intercell.tsv",
                    "dataset_version": "1.0.0",
                    "distribution": [
                        {
                            "@type": "cr:FileObject",
                            "@id": "intercell-file",
                            "contentUrl": "https://omnipathdb.org/intercell.tsv",
                            "encodingFormat": "text/tab-separated-values",
                            "name": "intercell.tsv",
                        }
                    ],
                    "recordSet": [
                        {
                            "@type": "cr:RecordSet",
                            "@id": "intercell-records",
                            "name": "records",
                            "field": [
                                {
                                    "@type": "cr:Field",
                                    "@id": "intercell-records/source",
                                    "name": "source",
                                    "dataType": "sc:Text",
                                    "examples": ["P53"],
                                    "description": "Source node",
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )

    dataset = state["datasets"][0]
    assert dataset["uiStatus"] == "detailed"
    assert dataset["distribution"][0]["contentUrl"] == "https://omnipathdb.org/intercell.tsv"
    assert dataset["recordSet"][0]["name"] == "records"
    assert dataset["uiFieldPreview"][0]["name"] == "source"
    assert dataset["uiFieldPreview"][0]["example"] == "P53"


def test_state_from_adapter_config_infers_field_preview_from_input_directory(tmp_path: Path) -> None:
    data_dir = tmp_path / "dataset"
    data_dir.mkdir()
    (data_dir / "sample.tsv").write_text("id\tname\n1\tAlice\n2\tBob\n", encoding="utf-8")

    state = web_ui_new._state_from_adapter_config(
        {
            "adapter": {
                "name": "Example Adapter",
                "description": "Adapter description",
                "version": "1.0.0",
                "license": "MIT",
                "code_repository": "https://example.org/repo",
                "keywords": ["adapter"],
                "creators": [{"name": "Alice"}],
            },
            "datasets": [
                {
                    "mode": "generate",
                    "input": str(data_dir),
                    "name": "Local Dataset",
                    "description": "Dataset with local sample",
                    "license": "MIT",
                    "url": "https://example.org/sample.tsv",
                    "dataset_version": "1.0.0",
                }
            ],
        }
    )

    dataset = state["datasets"][0]
    assert dataset["uiStatus"] == "detailed"
    assert dataset["distribution"][0]["encodingFormat"] == "text/tab-separated-values"
    assert dataset["distribution"][0]["sha256"]
    assert dataset["uiInferenceFileName"] == "sample.tsv"
    assert [field["name"] for field in dataset["uiFieldPreview"]] == ["id", "name"]


def test_state_from_payload_rejects_legacy_preload_schema() -> None:
    try:
        web_ui_new._state_from_payload(
            {
                "adapter": {
                    "name": "Example Adapter",
                    "description": "Adapter description",
                    "version": "1.0.0",
                    "license": "MIT",
                    "code_repository": "https://example.org/repo",
                    "keywords": ["adapter"],
                    "creators": [{"name": "Alice"}],
                },
                "datasets": [
                    {
                        "name": "Legacy Dataset",
                        "description": "Legacy preload shape",
                        "distribution": [{"contentUrl": "https://example.org/file.tsv"}],
                    }
                ],
            }
        )
    except ValueError as exc:
        assert "current adapter config schema" in str(exc) or "Dataset mode" in str(exc)
    else:
        raise AssertionError("Expected legacy preload schema to be rejected.")


def test_render_form_mentions_explicit_dataset_mode() -> None:
    page = web_ui_new._render_form()

    assert "Dataset mode" in page
    assert 'value="generate"' in page
    assert 'value="existing"' in page


def test_render_form_keeps_hidden_adapter_settings_only() -> None:
    page = web_ui_new._render_form()

    assert ">Settings<" not in page
    assert "Adapter ID" in page
    assert 'id="adapter_id_display"' in page
    assert 'name="adapter_id"' in page
    assert 'type="hidden"' in page
    assert 'name="validate"' in page
    assert 'name="output"' in page


def test_download_route_serves_latest_generated_file(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    output_path = tmp_path / "generated.jsonld"
    output_path.write_text('{"name":"generated"}', encoding="utf-8")

    class DummyResult:
        def __init__(self, output_path: Path) -> None:
            self.output_path = str(output_path)
            self.stdout = "ok"
            self.stderr = ""

    monkeypatch.setattr(web_ui_new, "_build_request_from_form", lambda data, output_dir=None: object())
    monkeypatch.setattr(
        web_ui_new,
        "execute_adapter_request",
        lambda request, generator: DummyResult(output_path),
    )

    handler = web_ui_new._Handler
    handler.output_dir = tmp_path
    handler.last_output_path = tmp_path / "default.jsonld"

    post_handler = object.__new__(handler)
    post_handler.path = "/"
    post_handler.headers = {"Content-Length": str(len("name=Example"))}
    post_handler.rfile = io.BytesIO(b"name=Example")
    post_events: list[tuple[int, str]] = []
    post_handler._send = lambda content, status=200: post_events.append((status, content))

    handler.do_POST(post_handler)

    assert post_events
    assert post_events[0][0] == 200

    get_handler = object.__new__(handler)
    get_handler.path = "/download"
    get_handler.wfile = io.BytesIO()
    sent_status: list[int] = []
    sent_headers: dict[str, str] = {}
    fallback_events: list[tuple[int, str]] = []
    get_handler.send_response = lambda status: sent_status.append(status)
    get_handler.send_header = lambda key, value: sent_headers.__setitem__(key, value)
    get_handler.end_headers = lambda: None
    get_handler._send = lambda content, status=200: fallback_events.append((status, content))

    handler.do_GET(get_handler)

    assert not fallback_events
    assert sent_status == [200]
    assert get_handler.wfile.getvalue().decode("utf-8") == '{"name":"generated"}'
    assert sent_headers["Content-Disposition"] == 'attachment; filename="generated.jsonld"'


def test_register_route_renders_registration_form(tmp_path: Path) -> None:
    handler = web_ui_new._Handler
    handler.output_dir = tmp_path
    handler.last_output_path = tmp_path / "generated.jsonld"
    handler.registration_db_path = tmp_path / "registry.sqlite3"

    get_handler = object.__new__(handler)
    get_handler.path = "/register"
    get_handler.wfile = io.BytesIO()
    events: list[tuple[int, str]] = []
    get_handler._send = lambda content, status=200: events.append((status, content))

    handler.do_GET(get_handler)

    assert events
    assert events[0][0] == 200
    assert "Register Adapter" in events[0][1]
    assert "contact_email" in events[0][1]
    assert "confirm_croissant_root" in events[0][1]
    assert "Create registration request" in events[0][1]


def test_register_route_stores_submission_in_sqlite(tmp_path: Path) -> None:
    handler = web_ui_new._Handler
    handler.output_dir = tmp_path
    handler.last_output_path = tmp_path / "generated.jsonld"
    handler.registration_db_path = tmp_path / "registry.sqlite3"

    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    body = (
        "adapter_name=Example+Adapter&"
        "contact_email=maintainer%40example.org&"
        "confirm_croissant_root=yes&"
        f"repository_location={repository}"
    ).encode("utf-8")

    post_handler = object.__new__(handler)
    post_handler.path = "/register"
    post_handler.headers = {"Content-Length": str(len(body))}
    post_handler.rfile = io.BytesIO(body)
    events: list[tuple[int, str]] = []
    post_handler._send = lambda content, status=200: events.append((status, content))

    handler.do_POST(post_handler)

    assert events
    assert events[0][0] == 200
    assert "Registration Detail" in events[0][1]
    assert "SUBMITTED" in events[0][1]
    assert "maintainer@example.org" in events[0][1]
    assert "Event History" in events[0][1]

    stored_id = events[0][1].split("Registration ID</div><div class=\"value\">", 1)[1].split(
        "</div>",
        1,
    )[0]
    registration = SQLiteRegistrationStore(handler.registration_db_path).get_registration(
        stored_id
    )

    assert registration is not None
    assert registration.contact_email == "maintainer@example.org"


def test_register_route_requires_croissant_root_confirmation(
    tmp_path: Path,
) -> None:
    handler = web_ui_new._Handler
    handler.output_dir = tmp_path
    handler.last_output_path = tmp_path / "generated.jsonld"
    handler.registration_db_path = tmp_path / "registry.sqlite3"

    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    body = (
        "adapter_name=Example+Adapter&"
        "contact_email=maintainer%40example.org&"
        f"repository_location={repository}"
    ).encode("utf-8")

    post_handler = object.__new__(handler)
    post_handler.path = "/register"
    post_handler.headers = {"Content-Length": str(len(body))}
    post_handler.rfile = io.BytesIO(body)
    events: list[tuple[int, str]] = []
    post_handler._send = lambda content, status=200: events.append((status, content))

    handler.do_POST(post_handler)

    assert events
    assert events[0][0] == 200
    assert "Please confirm that croissant.jsonld is located at the repository root." in events[0][1]
    assert "maintainer@example.org" in events[0][1]


def test_register_detail_route_renders_event_history(tmp_path: Path) -> None:
    handler = web_ui_new._Handler
    handler.output_dir = tmp_path
    handler.last_output_path = tmp_path / "generated.jsonld"
    handler.registration_db_path = tmp_path / "registry.sqlite3"

    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    store = SQLiteRegistrationStore(handler.registration_db_path)
    registration = submit_registration(
        adapter_name="Example Adapter",
        repository_location=str(repository),
        store=store,
    )

    get_handler = object.__new__(handler)
    get_handler.path = f"/register?registration_id={registration.registration_id}"
    get_handler.wfile = io.BytesIO()
    events: list[tuple[int, str]] = []
    get_handler._send = lambda content, status=200: events.append((status, content))

    handler.do_GET(get_handler)

    assert events
    assert events[0][0] == 200
    assert "Registration Detail" in events[0][1]
    assert registration.registration_id in events[0][1]
    assert "SUBMITTED" in events[0][1]


def test_register_process_route_shows_valid_created_event_and_canonical_entry(
    tmp_path: Path,
) -> None:
    handler = web_ui_new._Handler
    handler.output_dir = tmp_path
    handler.last_output_path = tmp_path / "generated.jsonld"
    handler.registration_db_path = tmp_path / "registry.sqlite3"

    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    (repository / "croissant.jsonld").write_text(
        json.dumps(_valid_adapter_document()),
        encoding="utf-8",
    )
    store = SQLiteRegistrationStore(handler.registration_db_path)
    registration = submit_registration(
        adapter_name="Example Adapter",
        repository_location=str(repository),
        store=store,
    )

    body = f"registration_id={registration.registration_id}".encode("utf-8")
    post_handler = object.__new__(handler)
    post_handler.path = "/register/process"
    post_handler.headers = {"Content-Length": str(len(body))}
    post_handler.rfile = io.BytesIO(body)
    events: list[tuple[int, str]] = []
    post_handler._send = lambda content, status=200: events.append((status, content))

    handler.do_POST(post_handler)

    assert events
    assert events[0][0] == 200
    assert "Registration Detail" in events[0][1]
    assert "VALID" in events[0][1]
    assert "VALID_CREATED" in events[0][1]
    assert "Current Canonical Entry" in events[0][1]
    assert "example-adapter::1.0.0" in events[0][1]


def test_registry_route_renders_active_sources_overview(tmp_path: Path) -> None:
    handler = web_ui_new._Handler
    handler.output_dir = tmp_path
    handler.last_output_path = tmp_path / "generated.jsonld"
    handler.registration_db_path = tmp_path / "registry.sqlite3"

    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    store = SQLiteRegistrationStore(handler.registration_db_path)
    registration = submit_registration(
        adapter_name="Example Adapter",
        repository_location=str(repository),
        store=store,
    )

    get_handler = object.__new__(handler)
    get_handler.path = "/registry"
    get_handler.wfile = io.BytesIO()
    events: list[tuple[int, str]] = []
    get_handler._send = lambda content, status=200: events.append((status, content))

    handler.do_GET(get_handler)

    assert events
    assert events[0][0] == 200
    assert "Registry Operations" in events[0][1]
    assert registration.registration_id in events[0][1]
    assert "Latest Event" in events[0][1]


def test_registry_route_renders_latest_persisted_refresh_summary(
    tmp_path: Path,
) -> None:
    handler = web_ui_new._Handler
    handler.output_dir = tmp_path
    handler.last_output_path = tmp_path / "generated.jsonld"
    handler.registration_db_path = tmp_path / "registry.sqlite3"
    store = SQLiteRegistrationStore(handler.registration_db_path)
    store.record_batch_refresh(
        BatchRefreshSummary(active_sources=1, processed=1, valid_created=1),
        started_at=datetime(2026, 4, 16, 12, 0, tzinfo=UTC),
        finished_at=datetime(2026, 4, 16, 12, 1, tzinfo=UTC),
    )

    get_handler = object.__new__(handler)
    get_handler.path = "/registry"
    get_handler.wfile = io.BytesIO()
    events: list[tuple[int, str]] = []
    get_handler._send = lambda content, status=200: events.append((status, content))

    handler.do_GET(get_handler)

    assert events
    assert events[0][0] == 200
    assert "Latest Batch Summary" in events[0][1]
    assert "VALID_CREATED" in events[0][1]


def test_registry_refresh_route_shows_batch_summary_and_source_outcomes(
    tmp_path: Path,
) -> None:
    handler = web_ui_new._Handler
    handler.output_dir = tmp_path
    handler.last_output_path = tmp_path / "generated.jsonld"
    handler.registration_db_path = tmp_path / "registry.sqlite3"

    valid_repo = tmp_path / "valid-repo"
    invalid_repo = tmp_path / "invalid-repo"
    valid_repo.mkdir()
    invalid_repo.mkdir()
    (valid_repo / "croissant.jsonld").write_text(
        json.dumps(
            _valid_adapter_document()
            | {"@id": "web-valid-adapter", "name": "Web Valid Adapter"}
        ),
        encoding="utf-8",
    )
    (invalid_repo / "croissant.jsonld").write_text(
        json.dumps(
            _invalid_adapter_document()
            | {"@id": "web-invalid-adapter", "name": "Web Invalid Adapter"}
        ),
        encoding="utf-8",
    )
    store = SQLiteRegistrationStore(handler.registration_db_path)
    submit_registration(
        adapter_name="Web Valid Adapter",
        repository_location=str(valid_repo),
        store=store,
    )
    submit_registration(
        adapter_name="Web Invalid Adapter",
        repository_location=str(invalid_repo),
        store=store,
    )

    post_handler = object.__new__(handler)
    post_handler.path = "/registry/refresh"
    post_handler.headers = {"Content-Length": "0"}
    post_handler.rfile = io.BytesIO(b"")
    events: list[tuple[int, str]] = []
    post_handler._send = lambda content, status=200: events.append((status, content))

    handler.do_POST(post_handler)

    assert events
    assert events[0][0] == 200
    assert "Registry Operations" in events[0][1]
    assert "Batch refresh finished." in events[0][1]
    assert "Latest Batch Summary" in events[0][1]
    assert "VALID_CREATED" in events[0][1]
    assert "INVALID" in events[0][1]
    assert "Web Valid Adapter" in events[0][1]
    assert "Web Invalid Adapter" in events[0][1]


def test_register_detail_shows_revalidate_action_for_invalid_source(
    tmp_path: Path,
) -> None:
    handler = web_ui_new._Handler
    handler.output_dir = tmp_path
    handler.last_output_path = tmp_path / "generated.jsonld"
    handler.registration_db_path = tmp_path / "registry.sqlite3"

    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    (repository / "croissant.jsonld").write_text(
        json.dumps(_invalid_adapter_document()),
        encoding="utf-8",
    )
    store = SQLiteRegistrationStore(handler.registration_db_path)
    registration = submit_registration(
        adapter_name="Example Adapter",
        repository_location=str(repository),
        store=store,
    )
    web_ui_new.finish_registration(
        registration_id=registration.registration_id,
        store=store,
    )

    get_handler = object.__new__(handler)
    get_handler.path = f"/register?registration_id={registration.registration_id}"
    get_handler.wfile = io.BytesIO()
    events: list[tuple[int, str]] = []
    get_handler._send = lambda content, status=200: events.append((status, content))

    handler.do_GET(get_handler)

    assert events
    assert events[0][0] == 200
    assert "Revalidate now" in events[0][1]
    assert "/register/revalidate" in events[0][1]


def test_register_revalidate_route_reprocesses_corrected_invalid_source(
    tmp_path: Path,
) -> None:
    handler = web_ui_new._Handler
    handler.output_dir = tmp_path
    handler.last_output_path = tmp_path / "generated.jsonld"
    handler.registration_db_path = tmp_path / "registry.sqlite3"

    repository = tmp_path / "adapter-repo"
    repository.mkdir()
    metadata_path = repository / "croissant.jsonld"
    metadata_path.write_text(
        json.dumps(_invalid_adapter_document()),
        encoding="utf-8",
    )
    store = SQLiteRegistrationStore(handler.registration_db_path)
    registration = submit_registration(
        adapter_name="Example Adapter",
        repository_location=str(repository),
        store=store,
    )
    web_ui_new.finish_registration(
        registration_id=registration.registration_id,
        store=store,
    )
    metadata_path.write_text(json.dumps(_valid_adapter_document()), encoding="utf-8")

    body = f"registration_id={registration.registration_id}".encode("utf-8")
    post_handler = object.__new__(handler)
    post_handler.path = "/register/revalidate"
    post_handler.headers = {"Content-Length": str(len(body))}
    post_handler.rfile = io.BytesIO(body)
    events: list[tuple[int, str]] = []
    post_handler._send = lambda content, status=200: events.append((status, content))

    handler.do_POST(post_handler)

    assert events
    assert events[0][0] == 200
    assert "Registration Detail" in events[0][1]
    assert "Registration revalidated successfully." in events[0][1]
    assert "VALID_CREATED" in events[0][1]
