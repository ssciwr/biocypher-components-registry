"""Tests for workspace_fs: file operations in-process and via the helper."""

import asyncio
import io
import json
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest

from src.core.workspace import workspace_fs as wfs
from tests.support.workspace_fakes import install_fake_sudo

HELPER = Path(wfs.__file__).resolve()


@pytest.fixture
def root(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    return workspace


@pytest.fixture(params=["in_process", "helper"])
def fs(request, root, monkeypatch):
    """The same WorkspaceFS API, unsandboxed and through the helper process."""
    if request.param == "helper":
        install_fake_sudo(monkeypatch)
        return wfs.WorkspaceFS(root, "sandbox1")
    return wfs.WorkspaceFS(root, None)


def run(coro):
    return asyncio.run(coro)


def test_write_read_list_edit(fs, root):
    run(fs.write_text("a/b.txt", "one two"))
    assert (root / "a/b.txt").read_text() == "one two"
    run(fs.edit_text("a/b.txt", "two", "2"))
    assert run(fs.read_text("a/b.txt")) == "one 2"
    (root / "z.txt").touch()
    assert run(fs.list_dir(".")) == [
        {"name": "a", "path": "a", "is_dir": True},
        {"name": "z.txt", "path": "z.txt", "is_dir": False},
    ]
    assert run(fs.list_dir("a")) == [
        {"name": "b.txt", "path": "a/b.txt", "is_dir": False}
    ]


@pytest.mark.parametrize(
    "call, kind",
    [
        (lambda fs: fs.read_text("../x"), wfs.INVALID_PATH),
        (lambda fs: fs.write_text("/etc/x", ""), wfs.INVALID_PATH),
        (lambda fs: fs.list_dir("missing"), wfs.NOT_FOUND),
        (lambda fs: fs.read_text("missing.txt"), wfs.NOT_FOUND),
        (lambda fs: fs.read_text("big.txt", max_bytes=3), wfs.TOO_LARGE),
        (lambda fs: fs.read_text("bin.dat"), wfs.NOT_TEXT),
        (lambda fs: fs.edit_text("big.txt", "zzz", "y"), wfs.EDIT_FAILED),
        (lambda fs: fs.edit_text("big.txt", "x", "y"), wfs.EDIT_FAILED),
    ],
)
def test_errors_carry_kind(fs, root, call, kind):
    (root / "big.txt").write_text("xxxx")
    (root / "bin.dat").write_bytes(b"\xff\xfe\x00")
    with pytest.raises(wfs.WorkspaceFSError) as excinfo:
        run(call(fs))
    assert excinfo.value.kind == kind


def test_symlink_escape_rejected(fs, root, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret").write_text("s")
    (root / "link").symlink_to(outside)
    with pytest.raises(wfs.WorkspaceFSError, match="escapes workspace root"):
        run(fs.read_text("link/secret"))


def test_archive_skips_excluded_and_symlinks(fs, root):
    (root / "a.py").write_text("a")
    (root / "sub").mkdir()
    (root / "sub/b.py").write_text("b")
    (root / ".venv").mkdir()
    (root / ".venv/x").write_text("x")
    (root / "link.py").symlink_to(root / "a.py")
    out = io.BytesIO()
    run(fs.archive(out, {".venv"}, 1_000_000))
    with ZipFile(io.BytesIO(out.getvalue())) as zf:
        assert sorted(zf.namelist()) == ["a.py", "sub/b.py"]


def test_archive_over_cap_is_too_large(fs, root):
    (root / "a.txt").write_bytes(bytes(range(256)) * 400)
    with pytest.raises(wfs.WorkspaceFSError) as excinfo:
        run(fs.archive(io.BytesIO(), set(), 100))
    assert excinfo.value.kind == wfs.TOO_LARGE


def test_helper_runs_as_given_user_via_sudo(root, monkeypatch):
    calls = install_fake_sudo(monkeypatch)
    run(wfs.WorkspaceFS(root, "sandbox7").list_dir("."))
    assert calls == [("sandbox7", [sys.executable, "-I", str(HELPER), "list_dir"])]


def test_helper_reports_non_json_failure(root, monkeypatch):
    monkeypatch.setattr(
        wfs, "sandbox_argv", lambda *a, **k: ["/bin/sh", "-c", "echo boom >&2; exit 1"]
    )
    with pytest.raises(wfs.WorkspaceFSError, match="boom") as excinfo:
        run(wfs.WorkspaceFS(root, "sandbox1").list_dir("."))
    assert excinfo.value.kind == wfs.OS_ERROR


def test_helper_rejects_bad_request(root):
    proc = subprocess.run(
        [sys.executable, "-I", str(HELPER), "no_such_op"],
        input=json.dumps({"root": str(root), "args": {}}),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2
    assert json.loads(proc.stderr)["message"].startswith("bad request")


def test_sandbox_argv_enters_cwd_as_user():
    argv = wfs.sandbox_argv(["ls"], {"PATH": "/bin"}, "sandbox1", cwd=Path("/w"))
    assert argv == [
        "sudo", "-n", "-u", "sandbox1", "--",
        "/usr/bin/env", "-i", "--chdir=/w", "PATH=/bin", "ls",
    ]  # fmt: skip
