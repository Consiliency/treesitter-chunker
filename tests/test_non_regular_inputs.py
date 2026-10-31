"""Non-regular source inputs are rejected without being opened.

Regression tests for treesitter-chunker#435. Opening a FIFO for reading blocks
until a writer appears, and a blocking read on a held-open pipe cannot reliably
be interrupted by SIGINT. The CLI and ``chunk_file`` therefore reject FIFOs,
devices, sockets and directories with ``os.stat`` before any open.

Every FIFO test runs the real CLI in a subprocess with a timeout and never
opens a writer. A regression blocks the child, and the test then fails with
``TimeoutExpired`` instead of hanging the suite.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from chunker import chunk_file
from chunker.core import ensure_regular_file
from chunker.exceptions import ChunkerError, NonRegularFileError
from chunker.repo.processor import RepoProcessor

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests/fixtures/boundary_ir/repos/python/app/service.py"
TIMEOUT_S = 30
MESSAGE = "is not a regular file"
GUIDANCE = "save the input to a file first"

requires_mkfifo = pytest.mark.skipif(
    not hasattr(os, "mkfifo"), reason="os.mkfifo is unavailable on this platform"
)


def _run(*args: str, cwd: Path, stdin: str | None = None):
    return subprocess.run(
        [sys.executable, "-m", "cli.main", *args],
        cwd=cwd,
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={
            **os.environ,
            "PYTHONUTF8": "1",
            "PYTHONPATH": os.pathsep.join(
                p for p in (str(REPO_ROOT), os.environ.get("PYTHONPATH")) if p
            ),
        },
        timeout=TIMEOUT_S,
        check=False,
    )


@pytest.fixture
def fifo(tmp_path: Path) -> Path:
    if not hasattr(os, "mkfifo"):
        pytest.skip("os.mkfifo is unavailable on this platform")
    path = tmp_path / "input.py"
    os.mkfifo(path)
    return path


@pytest.fixture
def regular(tmp_path: Path) -> Path:
    path = tmp_path / "service.py"
    path.write_bytes(FIXTURE.read_bytes())
    return path


@requires_mkfifo
@pytest.mark.parametrize("lang_args", [["-l", "python"], []])
def test_chunk_rejects_fifo_without_blocking(tmp_path, fifo, lang_args):
    result = _run("chunk", str(fifo), *lang_args, "--json", cwd=tmp_path)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert json.loads(result.stdout) == []
    assert MESSAGE in result.stderr
    assert "FIFO" in result.stderr
    assert GUIDANCE in result.stderr
    assert str(fifo) in result.stderr


@requires_mkfifo
def test_chunk_rejects_symlink_to_fifo(tmp_path, fifo):
    link = tmp_path / "link.py"
    link.symlink_to(fifo)
    result = _run("chunk", str(link), "-l", "python", "--json", cwd=tmp_path)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert MESSAGE in result.stderr


@requires_mkfifo
def test_batch_rejects_explicit_fifo_and_processes_regular_files(
    tmp_path, fifo, regular
):
    result = _run(
        "batch", str(fifo), str(regular), "-l", "python", "--json", "-q", cwd=tmp_path
    )
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert MESSAGE in result.stderr
    chunks = json.loads(result.stdout)
    assert chunks
    assert {c["file_path"] for c in chunks} == {str(regular)}


@requires_mkfifo
def test_batch_stdin_path_list_rejects_fifo(tmp_path, fifo, regular):
    result = _run(
        "batch",
        "--stdin",
        "-l",
        "python",
        "--json",
        "-q",
        cwd=tmp_path,
        stdin=f"{fifo}\n{regular}\n",
    )
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert MESSAGE in result.stderr
    assert {c["file_path"] for c in json.loads(result.stdout)} == {str(regular)}


@requires_mkfifo
@pytest.mark.parametrize("recursive", ["-r", "-R"])
def test_batch_directory_walk_skips_fifo(tmp_path, fifo, regular, recursive):
    result = _run(
        "batch", str(tmp_path), recursive, "-l", "python", "--json", "-q", cwd=tmp_path
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert {c["file_path"] for c in json.loads(result.stdout)} == {str(regular)}


@requires_mkfifo
def test_boundary_rejects_fifo_without_blocking(tmp_path, fifo):
    result = _run("boundary", str(fifo), "-l", "python", cwd=tmp_path)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert MESSAGE in result.stderr
    assert result.stdout == ""


@requires_mkfifo
def test_chunk_file_rejects_fifo_without_opening(tmp_path, fifo):
    code = (
        "import sys\n"
        "from chunker import chunk_file\n"
        "from chunker.exceptions import NonRegularFileError\n"
        "try:\n"
        "    chunk_file(sys.argv[1], 'python')\n"
        "except NonRegularFileError as exc:\n"
        "    print(exc.kind)\n"
        "    raise SystemExit(3)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code, str(fifo)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_S,
        check=False,
    )
    assert result.returncode == 3, (result.stdout, result.stderr)
    assert "FIFO" in result.stdout


@requires_mkfifo
def test_repo_walkers_skip_fifo(tmp_path, fifo, regular):
    for strategy in ("depth-first", "breadth-first"):
        processor = RepoProcessor(show_progress=False, traversal_strategy=strategy)
        files = processor.get_processable_files(str(tmp_path))
        assert fifo.resolve() not in files, strategy
        assert regular.resolve() in files, strategy


def test_chunk_rejects_directory(tmp_path):
    target = tmp_path / "pkg.py"
    target.mkdir()
    result = _run("chunk", str(target), "-l", "python", "--json", cwd=tmp_path)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert json.loads(result.stdout) == []
    assert MESSAGE in result.stderr
    assert "directory" in result.stderr


def test_chunk_file_rejects_directory(tmp_path):
    with pytest.raises(NonRegularFileError) as excinfo:
        chunk_file(tmp_path, "python")
    assert excinfo.value.kind == "directory"
    assert isinstance(excinfo.value, ChunkerError)
    assert GUIDANCE in str(excinfo.value)


def test_ensure_regular_file_missing_path_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        ensure_regular_file(tmp_path / "missing.py")


def _symlink_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlinks unavailable: {exc}")


def test_chunk_accepts_symlink_to_regular_file(tmp_path, regular):
    link = tmp_path / "link.py"
    _symlink_or_skip(link, regular)
    via_link = _run("chunk", str(link), "-l", "python", "--json", cwd=tmp_path)
    direct = _run("chunk", str(regular), "-l", "python", "--json", cwd=tmp_path)
    assert via_link.returncode == 0, (via_link.stdout, via_link.stderr)
    assert direct.returncode == 0, (direct.stdout, direct.stderr)
    linked_chunks = json.loads(via_link.stdout)
    assert linked_chunks
    assert [c["content"] for c in linked_chunks] == [
        c["content"] for c in json.loads(direct.stdout)
    ]


def test_chunk_file_accepts_symlink_to_regular_file(tmp_path, regular):
    link = tmp_path / "link.py"
    _symlink_or_skip(link, regular)
    ensure_regular_file(link)
    assert chunk_file(link, "python")
