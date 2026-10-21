"""Check workspace sandbox isolation inside the built Docker image.

Creates two workspaces the way the service does, owned by two pool users,
and verifies that neither session user can list, read or write the other's
workspace or inspect its processes, that the API user cannot read either
workspace directly, that file access through the session user still works,
and that teardown leaves nothing of a session behind. Exits non-zero on any
failure. Runs in CI (.github/workflows/isolation.yml).

The script is not part of the image; mount it and run it as apiuser (the
image default):

    docker build -t biocypher-registry .
    docker run --rm --init -e PYTHONPATH=/app \\
        -v "$PWD/scripts:/app/scripts:ro" biocypher-registry \\
        uv run --no-sync python scripts/check_workspace_isolation.py
"""

from __future__ import annotations

import asyncio
import io
import os
import sys
import uuid
from pathlib import Path

from src.core.workspace import client_loop as cl
from src.core.workspace import service
from src.core.workspace import workspace_fs as wfs

TEXT_FILE = "dir/a.txt"

failures: list[str] = []


def check(ok: bool, what: str) -> None:
    print(f"{'ok  ' if ok else 'FAIL'} {what}")
    if not ok:
        failures.append(what)


async def as_user(user: str, script: str, *args: str) -> tuple[int, str]:
    """Run a shell snippet as ``user``; return its exit code and stdout."""
    proc = await asyncio.create_subprocess_exec(
        *cl.sandbox_argv(["/bin/sh", "-c", script, "sh", *args], {}, user),
        cwd="/",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    out, _ = await proc.communicate()
    return proc.returncode, out.decode()


async def fails(user: str, script: str, *args: str) -> bool:
    return (await as_user(user, script, *args))[0] != 0


async def check_isolation(user_a, user_b, root, ws_a, ws_b) -> None:
    """Session A against session B's files and running command."""
    code, out = await as_user(user_b, 'pgrep -u "$(id -u)" sleep')
    pids = out.split()
    check(code == 0 and bool(pids), f"{user_b} runs a command")
    pid = pids[0] if pids else "0"

    check(await fails(user_a, 'ls "$1"', str(root)),
          f"{user_a} cannot list the workspaces root")
    check(await fails(user_a, 'ls "$1"', str(ws_b)),
          f"{user_a} cannot list {user_b}'s workspace")
    check(await fails(user_a, 'cat "$1/secret.txt"', str(ws_b)),
          f"{user_a} cannot read {user_b}'s file")
    check(await fails(user_a, 'touch "$1/x"', str(ws_b)),
          f"{user_a} cannot write into {user_b}'s workspace")
    await as_user(user_a, 'rm -rf "$1"', str(ws_b))
    check(ws_b.exists(), f"{user_a} cannot remove {user_b}'s workspace")
    check(await fails(user_a, 'readlink "/proc/$1/cwd"', pid),
          f"{user_a} cannot see the cwd of {user_b}'s process")
    check(await fails(user_a, 'cat "/proc/$1/environ"', pid),
          f"{user_a} cannot read the environment of {user_b}'s process")
    check(await fails(user_a, 'kill -0 "$1"', pid),
          f"{user_a} cannot signal {user_b}'s process")
    check(await fails(user_a, "ls /app/data"), f"{user_a} cannot list /app/data")
    check(await fails(user_a, "touch /app/.venv/x"),
          f"{user_a} cannot write to the service venv")

    try:
        os.listdir(ws_a)
        api_blocked = False
    except PermissionError:
        api_blocked = True
    check(api_blocked, "the API user cannot list a workspace directly")


async def check_session_access(user_a, ws_a, ws_b) -> None:
    """File tools, routes, download and run_command still work as the user."""
    fs_a = wfs.WorkspaceFS(ws_a, user_a)
    await fs_a.write_text(TEXT_FILE, "hello")
    await fs_a.edit_text(TEXT_FILE, "hello", "hello a")
    check(await fs_a.read_text(TEXT_FILE) == "hello a",
          "file write/edit/read as the session user")
    names = [e["name"] for e in await fs_a.list_dir(".")]
    check("dir" in names, "directory listing as the session user")
    out = io.BytesIO()
    await fs_a.archive(out, {".venv", ".cache"}, 10_000_000)
    check(out.getvalue()[:2] == b"PK", "zip download as the session user")
    try:
        await fs_a.read_text(f"../{ws_b.name}/secret.txt")
        escaped = True
    except wfs.WorkspaceFSError:
        escaped = False
    check(not escaped, "file access cannot leave the workspace")

    # Download over the cap: a clean error, and the helper does not linger.
    await fs_a.write_text("big.txt", os.urandom(300_000).hex())
    try:
        await fs_a.archive(io.BytesIO(), set(), 10_000)
        kind = None
    except wfs.WorkspaceFSError as e:
        kind = e.kind
    check(kind == wfs.TOO_LARGE, "download over the cap is refused")
    await asyncio.sleep(0.5)
    # [w]: the pattern must not match the shell running pgrep.
    check(await fails(user_a, 'pgrep -u "$(id -u)" -f "[w]orkspace_fs"'),
          "no zip helper left running after the refused download")

    tools = {
        t.name: t
        for t in cl.make_file_tools(
            get_fs=lambda: fs_a,
            get_exec_bin=lambda: service._exec_bin(ws_a, user_a),
        )
    }
    out = await tools["run_command"].call(
        {
            "command": 'id -un; pwd; python -c "import sys; print(sys.prefix)"; '
            'echo "$TMPDIR"'
        }
    )
    check(
        out == f"[exit 0]\n{user_a}\n{ws_a}\n{ws_a / '.venv'}\n{ws_a / wfs.TMP_DIR}\n",
        "run_command runs as the session user in its workspace, venv and TMPDIR",
    )


async def main() -> int:
    pool = service.sandbox_pool()
    if len(pool) < 2:
        print("sandbox pool not configured (AGENT_SANDBOX_USER_PREFIX/_POOL_SIZE)")
        return 2
    user_a, user_b = pool[0], pool[1]
    root = Path(os.getenv("AGENT_WORKSPACES_ROOT", "/app/data/workspaces"))
    # Session-style names, so the startup sweep removes them after a crash.
    ws_a = root / uuid.uuid4().hex
    ws_b = root / uuid.uuid4().hex
    leftover = f"/tmp/isolation-{uuid.uuid4().hex}"
    await service._make_workspace(ws_a, user_a)
    await service._make_workspace(ws_b, user_b)
    sleeper = None
    try:
        # Session B's file, a temp file and a running command, all through
        # the code paths the service uses.
        await wfs.WorkspaceFS(ws_b, user_b).write_text("secret.txt", "b-only")
        await as_user(user_b, 'echo b-only > "$1"', leftover)
        sleeper = await asyncio.create_subprocess_exec(
            *cl.sandbox_argv(
                ["/bin/sleep", "60"], cl._exec_env(home=ws_b), user_b, cwd=ws_b
            ),
            cwd=root,
        )
        await asyncio.sleep(0.5)
        await check_isolation(user_a, user_b, root, ws_a, ws_b)
        await check_session_access(user_a, ws_a, ws_b)
    finally:
        # Removal kills everything still running as the user (the sleeper)
        # and deletes the user's files in the shared temp directories.
        for ws, user in ((ws_a, user_a), (ws_b, user_b)):
            check(await service._remove_workspace(ws, user), f"{ws.name} removed")
        if sleeper is not None:
            code = await asyncio.wait_for(sleeper.wait(), timeout=10)
            check(code != 0, "teardown killed the command")
        check(await fails(user_b, 'test -e "$1"', leftover),
              f"teardown deleted {user_b}'s files in /tmp")

    print(f"\n{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
