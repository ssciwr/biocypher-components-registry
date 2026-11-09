from __future__ import annotations

import asyncio
import hashlib
import time
from pathlib import Path

from fastapi.testclient import TestClient

from src.api.routers import dataset_uploads
from src.api.app import create_app
from src.core.dataset.request import GenerationResult
from src.core.dataset.upload import service as upload_service
from src.core.dataset.upload.service import UploadSessionManager


def _create_payload(*, count: int = 1) -> dict[str, object]:
    return {
        "source_kind": "file" if count == 1 else "folder",
        "source_name": "dataset",
        "entries": [
            {
                "entry_id": f"entry-{index}",
                "relative_path": f"nested/data-{index}.csv",
                "original_size": 8,
                "logical_format": "csv",
                "artifact_mode": "complete",
                "strategy": "complete-file-v1",
                "artifact_size": 8,
            }
            for index in range(count)
        ],
        "generation": {
            "generator": "auto",
            "validate": True,
            "creators": [{"name": "Test Creator"}],
        },
    }


def test_upload_session_streams_reconciles_and_cleans_up(
    tmp_path: Path, monkeypatch
) -> None:
    manager = UploadSessionManager(scratch_root=tmp_path, require_tmpfs=False)
    manager.start()
    app = create_app(upload_session_manager=manager)
    app.state.upload_session_manager = manager
    client = TestClient(app)
    client.__enter__()
    processing_order: list[str] = []
    real_reconcile = dataset_uploads.reconcile_generated_metadata
    real_validate = dataset_uploads.validate_dataset

    def tracked_reconcile(document, session):
        processing_order.append("privacy-reconciliation")
        return real_reconcile(document, session)

    def tracked_validate(document):
        processing_order.append("croissant-validation")
        return real_validate(document)

    monkeypatch.setattr(dataset_uploads, "reconcile_generated_metadata", tracked_reconcile)
    monkeypatch.setattr(dataset_uploads, "validate_dataset", tracked_validate)

    def generated_result(*, request, generator, **_kwargs):
        return GenerationResult(
            output_path=request.output_path,
            warnings=["Croissant Baker did not describe 1 discovered file(s)."],
            document={
                "@context": {},
                "@type": "sc:Dataset",
                "distribution": [
                    {
                        "@type": "cr:FileObject",
                        "name": "data-0.csv",
                        "contentUrl": "nested/data-0.csv",
                        "sha256": hashlib.sha256(b"id,name\n").hexdigest(),
                        "examples": [["1", "Alice"]],
                    }
                ],
            },
        )

    monkeypatch.setattr(
        "src.api.routers.dataset_uploads.execute_dataset_request", generated_result
    )
    created = client.post("/api/v1/metadata/upload-sessions", json=_create_payload())
    assert created.status_code == 201
    assert created.headers["cache-control"].startswith("no-store")
    session = created.json()
    content = b"id,name\n"
    digest = hashlib.sha256(content).hexdigest()
    authorization = {"Authorization": f"Bearer {session['token']}"}
    uploaded = client.put(
        f"/api/v1/metadata/upload-sessions/{session['session_id']}/artifacts/entry-0",
        content=content,
        headers={
            **authorization,
            "X-Artifact-SHA256": digest,
            "X-Original-SHA256": digest,
        },
    )
    assert uploaded.status_code == 200
    session_root = tmp_path / session["session_id"]
    assert session_root.exists()

    finalized = client.post(
        f"/api/v1/metadata/upload-sessions/{session['session_id']}/finalize",
        headers=authorization,
    )
    assert finalized.status_code == 202
    for _ in range(100):
        polled = client.get(
            f"/api/v1/metadata/upload-sessions/{session['session_id']}",
            headers=authorization,
        )
        if polled.json()["status"] == "complete":
            break
        time.sleep(0.01)
    assert polled.json()["status"] == "complete"
    body = polled.json()["result"]
    file_object = body["metadata"]["distribution"][0]
    assert file_object["sha256"] == digest
    assert file_object["contentSize"] == "8"
    assert "examples" not in file_object
    assert "stdout" not in body
    assert "stderr" not in body
    assert body["warnings"] == [
        "Croissant Baker did not describe 1 discovered file(s)."
    ]
    assert processing_order == ["privacy-reconciliation", "croissant-validation"]
    assert not session_root.exists()
    client.__exit__(None, None, None)


def test_upload_routes_reject_1001_files_and_fail_closed_without_tmpfs(
    tmp_path: Path,
) -> None:
    enabled = UploadSessionManager(
        scratch_root=tmp_path / "enabled", require_tmpfs=False
    )
    enabled.start()
    app = create_app(upload_session_manager=enabled)
    app.state.upload_session_manager = enabled
    response = TestClient(app).post(
        "/api/v1/metadata/upload-sessions", json=_create_payload(count=1001)
    )
    assert response.status_code == 413
    assert response.headers["cache-control"].startswith("no-store")

    disabled = UploadSessionManager(scratch_root=tmp_path / "disk", require_tmpfs=True)
    disabled.start()
    disabled_app = create_app(upload_session_manager=disabled)
    disabled_app.state.upload_session_manager = disabled
    unavailable = TestClient(disabled_app).post(
        "/api/v1/metadata/upload-sessions", json=_create_payload()
    )
    assert unavailable.status_code == 503


def test_full_admission_capacity_returns_retry_after(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(upload_service, "MAX_ACTIVE_SESSIONS", 0)
    manager = UploadSessionManager(scratch_root=tmp_path, require_tmpfs=False)
    manager.start()
    app = create_app(upload_session_manager=manager)
    app.state.upload_session_manager = manager

    response = TestClient(app).post(
        "/api/v1/metadata/upload-sessions", json=_create_payload()
    )

    assert response.status_code == 429
    assert response.headers["retry-after"] == "15"
    assert "capacity" in response.json()["detail"].lower()


def test_generation_failure_hides_diagnostics_and_deletes_session(
    tmp_path: Path, monkeypatch
) -> None:
    manager = UploadSessionManager(scratch_root=tmp_path, require_tmpfs=False)
    manager.start()
    app = create_app(upload_session_manager=manager)
    app.state.upload_session_manager = manager
    client = TestClient(app)
    client.__enter__()
    created = client.post("/api/v1/metadata/upload-sessions", json=_create_payload())
    session = created.json()
    content = b"id,name\n"
    digest = hashlib.sha256(content).hexdigest()
    authorization = {"Authorization": f"Bearer {session['token']}"}
    uploaded = client.put(
        f"/api/v1/metadata/upload-sessions/{session['session_id']}/artifacts/entry-0",
        content=content,
        headers={
            **authorization,
            "X-Artifact-SHA256": digest,
            "X-Original-SHA256": digest,
        },
    )
    assert uploaded.status_code == 200

    def fail_generation(**_kwargs):
        raise RuntimeError("raw baker stderr containing a secret")

    monkeypatch.setattr(
        "src.api.routers.dataset_uploads.execute_dataset_request", fail_generation
    )

    failed = client.post(
        f"/api/v1/metadata/upload-sessions/{session['session_id']}/finalize",
        headers=authorization,
    )
    assert failed.status_code == 202
    for _ in range(100):
        polled = client.get(
            f"/api/v1/metadata/upload-sessions/{session['session_id']}",
            headers=authorization,
        )
        if polled.json()["status"] == "failed":
            break
        time.sleep(0.01)
    assert polled.json()["status"] == "failed"
    assert "raw baker stderr" not in polled.text
    assert not (tmp_path / session["session_id"]).exists()
    client.__exit__(None, None, None)
