"""Workspace file access, performed as the session's sandbox user.

Each session's workspace belongs to the pool user leased for that session
(mode 0700), so the API user cannot read it. Every file operation the API
performs on a workspace (the model's file tools, the file routes, the zip
download) therefore runs as that user:

- sandboxed: this file is executed as a script via ``sudo -u <user>``, with a
  JSON request on stdin; the result goes to stdout (JSON, or the raw zip for
  ``archive``) and a failure to stderr as JSON with a non-zero exit code;
- unsandboxed (local dev, tests): the same functions run in-process.

Path resolution happens inside the operation, as the same user, so a symlink
is resolved with that user's permissions and confined to the workspace.

Standard library only: the script runs with ``python -I`` and must not
import anything from the application.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import signal
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from zipfile import ZIP_DEFLATED, ZipFile

# Sandboxed workspaces' TMPDIR, relative to the workspace root.
TMP_DIR = ".tmp"

# Error kinds, mapped to HTTP status codes by the file routes.
INVALID_PATH = "invalid_path"
NOT_FOUND = "not_found"
TOO_LARGE = "too_large"
NOT_TEXT = "not_text"
EDIT_FAILED = "edit_failed"
OS_ERROR = "os_error"


class WorkspaceFSError(Exception):
    """A workspace file operation failed; ``kind`` is one of the kinds above."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


def resolve_in_root(path: str, root: Path) -> Path:
    """Resolve a tool-supplied path and confine it to ``root``.

    The untrusted input is validated before any path is constructed from it:
    absolute paths and ``..`` components are rejected outright, so only plain
    relative paths below the workspace root ever reach the filesystem. The
    final containment check guards against anything the component validation
    missed (e.g. symlinks inside the workspace pointing outside it).
    """
    candidate = PurePosixPath(path)
    if candidate.is_absolute() or PureWindowsPath(path).is_absolute():
        raise ValueError(f"absolute paths are not allowed: {path}")
    if any(part == ".." for part in candidate.parts):
        raise ValueError(f"path must not contain '..': {path}")
    root_str = str(root)
    normalized = os.path.normpath(os.path.join(root_str, path))
    if normalized != root_str and not normalized.startswith(root_str + os.sep):
        raise ValueError(f"path escapes workspace root: {path}")
    resolved = Path(normalized).resolve()
    if resolved != root and not resolved.is_relative_to(root):
        raise ValueError(f"path escapes workspace root: {path}")
    return resolved


def _resolve(root: str, path: str) -> Path:
    try:
        return resolve_in_root(path, Path(root))
    except ValueError as e:
        raise WorkspaceFSError(INVALID_PATH, str(e)) from None


# ------------------------------------------------------------ operations
# Each takes the workspace root as an absolute path string and returns a
# JSON-serializable value (archive writes to a binary stream instead).


def list_dir(root: str, path: str = ".") -> list[dict]:
    """Directory entries, directories first, each ``{name, path, is_dir}``."""
    target = _resolve(root, path)
    if not target.is_dir():
        raise WorkspaceFSError(NOT_FOUND, f"no such directory: {path}")
    try:
        entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name))
    except OSError as e:
        raise WorkspaceFSError(OS_ERROR, str(e)) from None
    return [
        {
            "name": e.name,
            "path": str(e.relative_to(root)),
            "is_dir": e.is_dir(),
        }
        for e in entries
    ]


def read_text(root: str, path: str, max_bytes: int | None = None) -> str:
    target = _resolve(root, path)
    if not target.is_file():
        raise WorkspaceFSError(NOT_FOUND, f"no such file: {path}")
    try:
        if max_bytes is not None and target.stat().st_size > max_bytes:
            raise WorkspaceFSError(TOO_LARGE, f"file too large: {path}")
        return target.read_text()
    except UnicodeDecodeError:
        raise WorkspaceFSError(NOT_TEXT, f"not a text file: {path}") from None
    except OSError as e:
        raise WorkspaceFSError(OS_ERROR, str(e)) from None


def write_text(root: str, path: str, content: str) -> None:
    target = _resolve(root, path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    except OSError as e:
        raise WorkspaceFSError(OS_ERROR, str(e)) from None


def edit_text(root: str, path: str, old_string: str, new_string: str) -> None:
    """Replace ``old_string``, which must occur exactly once."""
    text = read_text(root, path)
    count = text.count(old_string)
    if count == 0:
        raise WorkspaceFSError(EDIT_FAILED, "old_string not found in file")
    if count > 1:
        raise WorkspaceFSError(
            EDIT_FAILED,
            f"old_string occurs {count} times; add context to make it unique",
        )
    write_text(root, path, text.replace(old_string, new_string, 1))


def archive(root: str, out, excluded: list[str] = ()) -> None:
    """Zip the workspace's regular files (no symlinks) into ``out``.

    Top-level entries named in ``excluded`` are left out. ``out`` may be
    unseekable (the helper writes to stdout).
    """
    workspace = Path(root)
    try:
        with ZipFile(out, "w", ZIP_DEFLATED) as zf:
            for path in workspace.rglob("*"):
                relative = path.relative_to(workspace)
                if relative.parts[0] in excluded:
                    continue
                if path.is_file() and not path.is_symlink():
                    zf.write(path, relative)
    except (OSError, RuntimeError) as e:
        raise WorkspaceFSError(OS_ERROR, str(e)) from None


OPERATIONS = {
    "list_dir": list_dir,
    "read_text": read_text,
    "write_text": write_text,
    "edit_text": edit_text,
}


# --------------------------------------------------------- API-side access


def sandbox_argv(
    argv: list[str], env: dict[str, str], user: str | None, cwd: Path | None = None
) -> list[str]:
    """Prefix ``argv`` so it runs as ``user`` with exactly ``env``.

    sudo resets the environment, so ``env`` is re-applied through ``env -i``.
    ``cwd`` is entered as ``user`` (``env --chdir``): the calling user may not
    be allowed into a workspace. Without a user the argv is returned unchanged.
    """
    if not user:
        return argv
    prefix = ["sudo", "-n", "-u", user, "--", "/usr/bin/env", "-i"]
    if cwd is not None:
        prefix.append(f"--chdir={cwd}")
    return [*prefix, *(f"{k}={v}" for k, v in env.items()), *argv]


async def kill_group(proc, user: str | None) -> None:
    """SIGKILL a process group started with ``start_new_session``, then reap it.

    Sandboxed, ``proc`` is the root-owned sudo, which this process may not
    signal; its children belong to ``user``, so that user kills the group.
    """
    if user:
        killer = await asyncio.create_subprocess_exec(
            *sandbox_argv(["/bin/kill", "-KILL", "--", f"-{proc.pid}"], {}, user),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await killer.wait()
    else:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)
    await proc.wait()


def _helper_error(stderr: bytes, returncode: int) -> WorkspaceFSError:
    try:
        reply = json.loads(stderr)
        return WorkspaceFSError(reply["kind"], reply["message"])
    except (ValueError, KeyError, TypeError):
        # Not our JSON: sudo or the interpreter failed before the helper ran.
        detail = stderr.decode(errors="replace").strip()
        return WorkspaceFSError(
            OS_ERROR, f"workspace helper failed (exit {returncode}): {detail}"
        )


class WorkspaceFS:
    """File operations on one workspace, as ``user`` (None: as this process).

    ``root`` and ``user`` also tell run_command where and as whom to run.
    """

    def __init__(self, root: Path, user: str | None):
        self.root = root
        self.user = user

    def _argv(self, op: str) -> list[str]:
        helper = [sys.executable, "-I", str(Path(__file__).resolve()), op]
        return sandbox_argv(helper, {}, self.user)

    async def _spawn(self, op: str, stdout):
        return await asyncio.create_subprocess_exec(
            *self._argv(op),
            # The API user's own cwd may be closed to the pool user.
            cwd=self.root.parent,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
            stdin=asyncio.subprocess.PIPE,
            stdout=stdout,
            stderr=asyncio.subprocess.PIPE,
            # Own process group, so kill_group can end the helper as the user.
            start_new_session=True,
        )

    async def _call(self, op: str, **kwargs):
        if not self.user:
            return await asyncio.to_thread(OPERATIONS[op], str(self.root), **kwargs)
        request = json.dumps({"root": str(self.root), "args": kwargs}).encode()
        proc = await self._spawn(op, asyncio.subprocess.PIPE)
        try:
            out, err = await proc.communicate(request)
        except BaseException:
            await kill_group(proc, self.user)
            raise
        if proc.returncode:
            raise _helper_error(err, proc.returncode)
        return json.loads(out)

    async def list_dir(self, path: str = ".") -> list[dict]:
        return await self._call("list_dir", path=path)

    async def read_text(self, path: str, max_bytes: int | None = None) -> str:
        return await self._call("read_text", path=path, max_bytes=max_bytes)

    async def write_text(self, path: str, content: str) -> None:
        await self._call("write_text", path=path, content=content)

    async def edit_text(self, path: str, old_string: str, new_string: str) -> None:
        await self._call(
            "edit_text", path=path, old_string=old_string, new_string=new_string
        )

    async def archive(self, out, excluded, max_bytes: int) -> None:
        """Write the workspace zip to the binary file ``out``.

        Raises ``WorkspaceFSError(TOO_LARGE)`` once the archive exceeds
        ``max_bytes``; ``out`` then holds a partial archive.
        """
        if not self.user:
            await asyncio.to_thread(
                archive, str(self.root), _CappedWriter(out, max_bytes), list(excluded)
            )
            return
        request = json.dumps(
            {"root": str(self.root), "args": {"excluded": list(excluded)}}
        ).encode()
        proc = await self._spawn("archive", asyncio.subprocess.PIPE)
        proc.stdin.write(request)
        proc.stdin.close()
        stderr_task = asyncio.create_task(proc.stderr.read())
        writer = _CappedWriter(out, max_bytes)
        try:
            while chunk := await proc.stdout.read(65536):
                await asyncio.to_thread(writer.write, chunk)
        except BaseException:
            # Over the cap or cancelled (client gone): stop the helper.
            stderr_task.cancel()
            await kill_group(proc, self.user)
            raise
        err = await stderr_task
        if await proc.wait():
            raise _helper_error(err, proc.returncode)


class _CappedWriter:
    """Binary write-only stream that refuses to grow past ``limit`` bytes."""

    def __init__(self, out, limit: int):
        self.out = out
        self.limit = limit
        self.written = 0

    def write(self, data: bytes) -> int:
        self.written += len(data)
        if self.written > self.limit:
            raise WorkspaceFSError(TOO_LARGE, "workspace archive too large")
        return self.out.write(data)

    def flush(self) -> None:
        self.out.flush()


# ----------------------------------------------------------- helper entry


def main(argv: list[str]) -> int:
    """Run one operation as the helper process (see module docstring)."""
    try:
        op = argv[1]
        request = json.load(sys.stdin)
        root, args = request["root"], request["args"]
        if op == "archive":
            archive(root, sys.stdout.buffer, **args)
        else:
            json.dump(OPERATIONS[op](root, **args), sys.stdout)
    except WorkspaceFSError as e:
        json.dump({"kind": e.kind, "message": str(e)}, sys.stderr)
        return 1
    except (IndexError, KeyError, TypeError, ValueError) as e:
        json.dump({"kind": OS_ERROR, "message": f"bad request: {e}"}, sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    os.umask(0o077)
    sys.exit(main(sys.argv))
