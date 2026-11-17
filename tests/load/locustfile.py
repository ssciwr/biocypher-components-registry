"""Load scenarios for the ephemeral upload API.

Each user performs LOAD_JOBS_PER_USER generations. The workload is shaped by:

* LOAD_FILES       files per session (1 sends a single file, more send a folder)
* LOAD_FILE_BYTES  bytes per file; 0 sends a 22-byte CSV
* LOAD_COLUMNS     CSV columns when LOAD_FILE_BYTES is set
* LOAD_THINK_SECONDS  pause between one user's jobs (0 keeps the default 0.1-0.5 s)
"""

from __future__ import annotations

import hashlib
import os
import random
import time
import uuid

import gevent
from gevent import sleep
from locust import HttpUser, events, task
from locust.exception import StopUser

MAX_ARTIFACT_BYTES = 1024 * 1024
MAX_SESSION_BYTES = 50 * 1024 * 1024
FILES = int(os.getenv("LOAD_FILES", "1"))
FILE_BYTES = int(os.getenv("LOAD_FILE_BYTES", "0"))
COLUMNS = int(os.getenv("LOAD_COLUMNS", "2"))
JOBS_PER_USER = int(os.getenv("LOAD_JOBS_PER_USER", "1"))
THINK_SECONDS = float(os.getenv("LOAD_THINK_SECONDS", "0"))
ADMISSION_TIMEOUT_SECONDS = int(os.getenv("LOAD_ADMISSION_TIMEOUT_SECONDS", "900"))
RESULT_TIMEOUT_SECONDS = int(os.getenv("LOAD_RESULT_TIMEOUT_SECONDS", "900"))
CSV_FLUSH_GRACE_SECONDS = 7


def _build_artifact() -> bytes:
    """Return a deterministic CSV of whole rows, at most FILE_BYTES long."""
    if FILE_BYTES <= 0:
        return b"id,name\n1,Alice\n2,Bob\n"
    if FILE_BYTES > MAX_ARTIFACT_BYTES or FILES * FILE_BYTES > MAX_SESSION_BYTES:
        raise SystemExit("LOAD_FILES x LOAD_FILE_BYTES exceeds the upload limits.")
    rng = random.Random(7)
    lines = [",".join(f"col_{i}" for i in range(COLUMNS)) + "\n"]
    size = len(lines[0])
    while True:
        cells = (
            str(rng.randint(0, 10**6))
            if i % 3 == 0
            else f"{rng.random():.6f}"
            if i % 3 == 1
            else "".join(rng.choices("abcdefghij", k=8))
            for i in range(COLUMNS)
        )
        row = ",".join(cells) + "\n"
        if size + len(row) > FILE_BYTES:
            return "".join(lines).encode()
        lines.append(row)
        size += len(row)


ARTIFACT = _build_artifact()
ARTIFACT_SHA256 = hashlib.sha256(ARTIFACT).hexdigest()

REJECTED_ROW = "admission rejected (429)"
END_TO_END_ROW = "END-TO-END admission to complete"

# Locust replaces stopped users while ramping up, so jobs are handed out as
# tickets: a run performs exactly as many generations as the configured users.
_jobs = {"total": None, "started": 0, "finished": 0}


@events.test_start.add_listener
def _reset_jobs(environment, **_kwargs) -> None:
    _jobs.update(total=None, started=0, finished=0)


def _take_job(environment) -> bool:
    if _jobs["total"] is None:
        _jobs["total"] = environment.runner.target_user_count * JOBS_PER_USER
    if _jobs["started"] >= _jobs["total"]:
        return False
    _jobs["started"] += 1
    return True


def _finish_job(environment) -> None:
    _jobs["finished"] += 1
    # Headless runs end by themselves; the web UI stays open for the next test.
    # Quitting waits for Locust's CSV writer, which flushes every 5 seconds.
    if _jobs["finished"] >= _jobs["total"] and environment.web_ui is None:
        gevent.spawn_later(CSV_FLUSH_GRACE_SECONDS, environment.runner.quit)


class CroissantGenerationUser(HttpUser):
    """Execute the same create/upload/finalize/poll sequence as the browser."""

    jobs_done = 0

    def wait_time(self) -> float:
        if THINK_SECONDS <= 0:
            return random.uniform(0.1, 0.5)
        return THINK_SECONDS * random.uniform(0.5, 1.5)

    @task
    def generate_once(self) -> None:
        if not _take_job(self.environment):
            raise StopUser()
        started = time.monotonic()
        completed = False
        try:
            session = self._wait_for_admission()
            if session is not None:
                completed = self._upload_finalize_and_wait(session)
        finally:
            error = None if completed else Exception("generation did not complete")
            elapsed_ms = (time.monotonic() - started) * 1000
            self._record(END_TO_END_ROW, "JOB", elapsed_ms, error)
            _finish_job(self.environment)
        self.jobs_done += 1
        if self.jobs_done >= JOBS_PER_USER:
            raise StopUser()

    def _record(self, name: str, kind: str, milliseconds: float, error=None) -> None:
        self.environment.events.request.fire(
            request_type=kind,
            name=name,
            response_time=milliseconds,
            response_length=0,
            exception=error,
            context={},
        )

    def _wait_for_admission(self) -> dict[str, str] | None:
        deadline = time.monotonic() + ADMISSION_TIMEOUT_SECONDS
        source_name = f"locust-{uuid.uuid4().hex}" + (".csv" if FILES == 1 else "")
        payload = {
            "source_kind": "file" if FILES == 1 else "folder",
            "source_name": source_name,
            "entries": [
                {
                    "entry_id": entry_id,
                    "relative_path": source_name if FILES == 1 else relative_path,
                    "original_size": len(ARTIFACT),
                    "artifact_size": len(ARTIFACT),
                    "logical_format": "csv",
                    "artifact_mode": "complete",
                    "strategy": "complete-file-v1",
                }
                for entry_id, relative_path in _entries()
            ],
            "generation": {
                "generator": "auto",
                "validate": True,
                "name": source_name,
                "creators": [{"name": "Phase 9 load test"}],
            },
        }

        while time.monotonic() < deadline:
            with self.client.post(
                "/api/v1/metadata/upload-sessions",
                json=payload,
                name="POST upload session admission",
                catch_response=True,
            ) as response:
                if response.status_code == 201:
                    response.success()
                    return response.json()
                if response.status_code == 429:
                    retry_after = _bounded_retry_after(
                        response.headers.get("Retry-After")
                    )
                    if time.monotonic() + retry_after >= deadline:
                        response.failure("admission did not succeed before timeout")
                        return None
                    response.success()
                    self._record(REJECTED_ROW, "EVENT", 0)
                else:
                    response.failure(
                        f"unexpected admission response {response.status_code}"
                    )
                    return None
            sleep(retry_after)

        return None

    def _upload_finalize_and_wait(self, session: dict[str, str]) -> bool:
        session_id = session["session_id"]
        authorization = {"Authorization": f"Bearer {session['token']}"}
        session_path = f"/api/v1/metadata/upload-sessions/{session_id}"

        for entry_id, _ in _entries():
            upload = self.client.put(
                f"{session_path}/artifacts/{entry_id}",
                data=ARTIFACT,
                headers={
                    **authorization,
                    "Content-Type": "text/csv",
                    "X-Artifact-SHA256": ARTIFACT_SHA256,
                    "X-Original-SHA256": ARTIFACT_SHA256,
                },
                name="PUT upload artifact",
            )
            if upload.status_code != 200:
                self._delete(session_path, authorization)
                return False

        finalized = self.client.post(
            f"{session_path}/finalize",
            headers=authorization,
            name="POST finalize generation",
        )
        if finalized.status_code != 202:
            self._delete(session_path, authorization)
            return False

        deadline = time.monotonic() + RESULT_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            with self.client.get(
                session_path,
                headers=authorization,
                name="GET generation status",
                catch_response=True,
            ) as response:
                if response.status_code != 200:
                    response.failure(f"status polling returned {response.status_code}")
                    return False
                status = response.json().get("status")
                if status == "complete":
                    response.success()
                    return True
                if status == "failed":
                    response.failure("generation failed")
                    return False
                retry_after = _bounded_retry_after(response.headers.get("Retry-After"))
                if time.monotonic() + retry_after >= deadline:
                    response.failure("generation did not finish before timeout")
                    return False
                response.success()
            sleep(retry_after)
        return False

    def _delete(self, session_path: str, headers: dict[str, str]) -> None:
        self.client.delete(
            session_path,
            headers=headers,
            name="DELETE failed load-test session",
        )


def _entries() -> list[tuple[str, str]]:
    if FILES == 1:
        return [("data", "data.csv")]
    return [(f"file-{i:04d}", f"data/part-{i:04d}.csv") for i in range(FILES)]


def _bounded_retry_after(value: str | None) -> int:
    try:
        return min(30, max(1, int(value or "1")))
    except ValueError:
        return 1
