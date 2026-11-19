"""Bounded subprocess execution for dataset generation backends."""

from __future__ import annotations

import os
import selectors
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from src.core.dataset.upload.limits import (
    GENERATOR_TIMEOUT_SECONDS,
    MAX_DIAGNOSTIC_BYTES,
    MAX_GENERATED_JSON_BYTES,
)


@dataclass(frozen=True, slots=True)
class BoundedProcessResult:
    """The bounded diagnostics and exit status of a child process."""

    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


def run_bounded_process(
    command: list[str], *, scratch_directory: Path
) -> BoundedProcessResult:
    """Run a child with a secret-free environment, limits, and bounded output."""
    scratch_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    environment = {
        "PATH": os.environ.get("PATH", os.defpath),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONUTF8": "1",
        "HOME": str(scratch_directory),
        "TMPDIR": str(scratch_directory),
        "XDG_CACHE_HOME": str(scratch_directory / ".cache"),
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
        "PYTHONPATH": str(Path(__file__).resolve().parents[3]),
    }
    limiter = shutil.which("prlimit")
    if limiter is None:
        raise RuntimeError("The required process limiter 'prlimit' is unavailable.")
    file_limit = MAX_GENERATED_JSON_BYTES + 1024 * 1024
    limited_command = [
        limiter,
        f"--as={1024 * 1024 * 1024}:{1024 * 1024 * 1024}",
        f"--cpu={GENERATOR_TIMEOUT_SECONDS + 1}:{GENERATOR_TIMEOUT_SECONDS + 1}",
        f"--fsize={file_limit}:{file_limit}",
        "--nofile=64:64",
        "--",
        *command,
    ]
    process = subprocess.Popen(
        limited_command,
        cwd=scratch_directory,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    stdout, stderr, timed_out = _drain_process(process)
    return BoundedProcessResult(
        returncode=process.returncode,
        stdout=stdout.decode("utf-8", errors="replace"),
        stderr=stderr.decode("utf-8", errors="replace"),
        timed_out=timed_out,
    )


def _drain_process(process: subprocess.Popen[bytes]) -> tuple[bytes, bytes, bool]:
    if process.stdout is None or process.stderr is None:  # pragma: no cover - defensive
        raise RuntimeError("Generator diagnostics were not captured.")
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    deadline = time.monotonic() + GENERATOR_TIMEOUT_SECONDS
    timed_out = False
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0 and process.poll() is None:
                timed_out = True
                os.killpg(process.pid, signal.SIGKILL)
            _read_available_output(selector, buffers, remaining)
            if timed_out and process.poll() is not None and not selector.get_map():
                break
        process.wait()
    finally:
        selector.close()
        process.stdout.close()
        process.stderr.close()
    return bytes(buffers["stdout"]), bytes(buffers["stderr"]), timed_out


def _read_available_output(
    selector: selectors.BaseSelector,
    buffers: dict[str, bytearray],
    remaining: float,
) -> None:
    """Drain ready diagnostic streams without exceeding their byte limits."""
    timeout = max(0.0, min(0.2, remaining))
    for key, _ in selector.select(timeout=timeout):
        chunk = os.read(key.fileobj.fileno(), 64 * 1024)
        if not chunk:
            selector.unregister(key.fileobj)
            continue
        destination = buffers[key.data]
        capacity = MAX_DIAGNOSTIC_BYTES - len(destination)
        if capacity > 0:
            destination.extend(chunk[:capacity])
