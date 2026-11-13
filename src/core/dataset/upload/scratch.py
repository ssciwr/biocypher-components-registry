"""RAM-backed scratch verification and secure session directories."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from src.core.dataset.upload.limits import EXPECTED_SCRATCH_FILESYSTEM


def verify_tmpfs_mount(root: Path) -> tuple[bool, str]:
    """Verify that ``root`` is backed by a restrictive Linux tmpfs mount."""
    if not root.exists() or not root.is_dir():
        return False, f"Ephemeral upload scratch does not exist: {root}"
    try:
        mount_lines = (
            Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines()
        )
    except OSError:
        return False, "Cannot verify the ephemeral upload scratch filesystem."

    candidates = _mount_candidates(mount_lines, root.resolve())
    if not candidates:
        return False, "Cannot locate the ephemeral upload scratch mount."
    _, filesystem, options = max(candidates, key=lambda candidate: candidate[0])
    if filesystem != EXPECTED_SCRATCH_FILESYSTEM:
        return False, f"Upload scratch must use tmpfs, found {filesystem}."
    required = {"noexec", "nosuid", "nodev"}
    missing = sorted(required - options)
    if missing:
        return False, "Upload scratch is missing mount options: " + ", ".join(missing)
    if not os.access(root, os.W_OK | os.X_OK):
        return False, "Upload scratch is not writable by the API process."
    return True, ""


def _mount_candidates(
    mount_lines: list[str], resolved: Path
) -> list[tuple[int, str, set[str]]]:
    """Return mount entries containing the resolved scratch path."""
    candidates: list[tuple[int, str, set[str]]] = []
    for line in mount_lines:
        candidate = _mount_candidate(line, resolved)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _mount_candidate(line: str, resolved: Path) -> tuple[int, str, set[str]] | None:
    """Parse one applicable Linux mountinfo line."""
    before, separator, after = line.partition(" - ")
    if not separator:
        return None
    fields = before.split()
    after_fields = after.split()
    if len(fields) < 6 or not after_fields:
        return None
    mount_point = Path(fields[4].replace("\\040", " "))
    try:
        resolved.relative_to(mount_point)
    except ValueError:
        return None
    options = set(fields[5].split(","))
    if len(after_fields) >= 3:
        options.update(after_fields[2].split(","))
    return len(mount_point.parts), after_fields[0], options


def prepare_scratch_root(root: Path, *, require_tmpfs: bool) -> tuple[bool, str]:
    """Prepare test scratch or fail closed when production tmpfs is unavailable."""
    if not require_tmpfs:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(root, 0o700)
        return True, ""
    return verify_tmpfs_mount(root)


def remove_scratch_tree(path: Path) -> None:
    """Idempotently remove one server-created scratch tree."""
    shutil.rmtree(path, ignore_errors=True)
