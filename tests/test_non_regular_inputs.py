"""Non-regular source inputs are rejected without being opened.

Regression tests for treesitter-chunker#435. Opening a FIFO for reading blocks
until a writer appears, and a blocking read on a held-open pipe cannot reliably
be interrupted by SIGINT. The CLI and ``chunk_file`` therefore reject FIFOs,
devices, sockets and directories with ``os.stat`` before any open.

Every FIFO test runs in a subprocess (the real CLI or a short Python script)
with a timeout and never opens a writer. A regression blocks the child, and the test then fails with
``TimeoutExpired`` instead of hanging the suite.
"""

from __future__ import annotations

import json
import os
import pickle
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from chunker import chunk_file
from chunker.core import ensure_regular_file
from chunker.exceptions import ChunkerError, NonRegularFileError
from chunker.parallel import ParallelChunker

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests/fixtures/boundary_ir/repos/python/app/service.py"
TIMEOUT_S = 30
MESSAGE = "is not a regular file"
GUIDANCE = "Save the input to a regular file first."
DIRECTORY_GUIDANCE = "pass it to the batch command instead"

requires_mkfifo = pytest.mark.skipif(
    not hasattr(os, "mkfifo"), reason="os.mkfifo is unavailable on this platform"
)


def _env(**extra: str) -> dict[str, str]:
    return {
        **os.environ,
        "PYTHONUTF8": "1",
        "PYTHONPATH": os.pathsep.join(
            p for p in (str(REPO_ROOT), os.environ.get("PYTHONPATH")) if p
        ),
        **extra,
    }


def _run(*args: str, cwd: Path, stdin: str | None = None):
    return subprocess.run(
        [sys.executable, "-m", "cli.main", *args],
        cwd=cwd,
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_env(),
        timeout=TIMEOUT_S,
        check=False,
    )


def _run_python(code: str, *args: str, cwd: Path, **env: str):
    """Run ``code`` in a child interpreter, bounded by ``TIMEOUT_S``."""
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code), *args],
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_env(**env),
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
@pytest.mark.parametrize("strategy", ["depth-first", "breadth-first"])
def test_repo_walkers_skip_fifo(tmp_path, fifo, regular, strategy):
    # process_repository both lists and reads the files, so a walker that
    # yielded the FIFO would block the child on open.
    code = """
        import json, sys
        from chunker.repo.processor import RepoProcessor
        processor = RepoProcessor(show_progress=False, traversal_strategy=sys.argv[2])
        result = processor.process_repository(sys.argv[1], incremental=False)
        print(json.dumps({
            "files": sorted(r.file_path for r in result.file_results),
            "chunks": {r.file_path: len(r.chunks) for r in result.file_results},
            "errors": sorted(result.errors),
        }))
    """
    result = _run_python(code, str(tmp_path), strategy, cwd=REPO_ROOT)
    assert result.returncode == 0, (result.stdout, result.stderr)
    report = json.loads(result.stdout.strip().splitlines()[-1])
    assert report["files"] == [regular.name]
    assert report["chunks"][regular.name] > 0
    assert report["errors"] == []


def _git_or_skip() -> str:
    git = shutil.which("git")
    if git is None:
        pytest.skip("git is unavailable")
    return git


@requires_mkfifo
@pytest.mark.parametrize("with_excludes_file", [False, True])
def test_git_processor_skips_fifo_gitignore(tmp_path, regular, with_excludes_file):
    git = _git_or_skip()
    isolated_git = {
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "HOME": str(tmp_path),
    }
    subprocess.run(
        [git, "init", "-q", str(tmp_path)],
        env={**os.environ, **isolated_git},
        check=True,
        timeout=TIMEOUT_S,
    )
    (tmp_path / "ignored.py").write_text("x = 1\n", encoding="utf-8")
    if with_excludes_file:
        # Non-empty patterns route get_processable_files into the git-backed
        # filter, and git itself would block opening the FIFO .gitignore.
        excludes = tmp_path / "excludes.txt"
        excludes.write_text("ignored.py\nexcludes.txt\n", encoding="utf-8")
        subprocess.run(
            [git, "-C", str(tmp_path), "config", "core.excludesfile", str(excludes)],
            env={**os.environ, **isolated_git},
            check=True,
            timeout=TIMEOUT_S,
        )
    os.mkfifo(tmp_path / ".gitignore")
    code = """
        import json, sys
        from chunker.repo.processor import GitAwareRepoProcessor
        processor = GitAwareRepoProcessor(show_progress=False)
        files = processor.get_processable_files(sys.argv[1])
        print(json.dumps(sorted(p.name for p in files)))
    """
    result = _run_python(code, str(tmp_path), cwd=REPO_ROOT, **isolated_git)
    assert result.returncode == 0, (result.stdout, result.stderr)
    names = json.loads(result.stdout.strip().splitlines()[-1])
    assert ".gitignore" not in names
    assert regular.name in names
    assert ("ignored.py" in names) is not with_excludes_file
    assert "not a regular file" in result.stderr


@requires_mkfifo
def test_watch_deltas_skip_fifo(tmp_path, fifo, regular):
    code = """
        import json, sys
        from pathlib import Path
        from chunker.repo.processor import GitAwareRepoProcessor
        processor = GitAwareRepoProcessor(show_progress=False)
        deltas = processor._build_watch_deltas(
            Path(sys.argv[1]), [sys.argv[2], sys.argv[3]], set()
        )
        print(json.dumps({
            "files": sorted({Path(n["file"]).name for n in deltas["nodes_added"]}),
            "errors": deltas.get("errors", []),
        }))
    """
    result = _run_python(code, str(tmp_path), fifo.name, regular.name, cwd=REPO_ROOT)
    assert result.returncode == 0, (result.stdout, result.stderr)
    report = json.loads(result.stdout.strip().splitlines()[-1])
    assert report == {"files": [regular.name], "errors": []}


_AUTO_CHUNK_SCRIPT = """
    import sys
    from chunker.auto import ZeroConfigAPI
    from chunker.exceptions import NonRegularFileError

    class Registry:
        def is_language_installed(self, language):
            return language == "python"
        def list_available_languages(self):
            return []
        def install_language(self, language, version=None):
            return False
        def get_language_version(self, language):
            return None
        def update_language(self, language):
            return False, None

    language = sys.argv[2] or None
    token_limit = int(sys.argv[3]) or None
    try:
        ZeroConfigAPI(Registry()).auto_chunk_file(
            sys.argv[1], language=language, token_limit=token_limit
        )
    except NonRegularFileError as exc:
        print(exc.kind)
        raise SystemExit(3)
"""


@requires_mkfifo
@pytest.mark.parametrize(
    ("name", "language", "token_limit"),
    [
        # No language: extension lookup fails, so shebang detection would open.
        pytest.param("input.unknownext", "", 0, id="shebang-detection"),
        # Explicit language that is not installed: the text fallback would read.
        pytest.param("input.py", "nosuchlanguage", 0, id="unknown-language"),
        # chunk_file_with_token_limit reads the path without chunk_file's check.
        pytest.param("input.py", "python", 100, id="token-limit"),
    ],
)
def test_auto_chunk_file_rejects_fifo(tmp_path, name, language, token_limit):
    path = tmp_path / name
    os.mkfifo(path)
    result = _run_python(
        _AUTO_CHUNK_SCRIPT, str(path), language, str(token_limit), cwd=REPO_ROOT
    )
    assert result.returncode == 3, (result.stdout, result.stderr)
    assert "FIFO" in result.stdout


@requires_mkfifo
@pytest.mark.parametrize(
    "command",
    [
        pytest.param(["ast", "{fifo}"], id="ast"),
        pytest.param(["ast", "{fifo}", "--chunks"], id="ast-chunks"),
        pytest.param(["query", "(identifier) @id", "-f", "{fifo}"], id="query"),
        pytest.param(["chunks", "{fifo}"], id="chunks"),
        pytest.param(["explore", "-f", "{fifo}"], id="explore"),
        pytest.param(["validate", "{fifo}"], id="validate"),
        pytest.param(["repl", "-f", "{fifo}"], id="repl"),
    ],
)
def test_debug_commands_reject_fifo(tmp_path, fifo, command):
    args = [part.format(fifo=fifo) for part in command]
    result = _run("debug", *args, "-l", "python", cwd=tmp_path, stdin="")
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert MESSAGE in result.stderr
    assert "FIFO" in result.stderr
    assert str(fifo) in result.stderr


@requires_mkfifo
def test_debug_repl_load_rejects_fifo(tmp_path, fifo):
    code = """
        import sys
        from chunker.debug.interactive.repl import DebugREPL
        repl = DebugREPL()
        repl._load_file(sys.argv[1])
        assert repl.current_code is None or repl.current_code == "", repl.current_code
        assert repl.current_file is None
    """
    result = _run_python(code, str(fifo), cwd=REPO_ROOT)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert MESSAGE in result.stdout


@requires_mkfifo
@pytest.mark.parametrize("source", ["paths", "stdin"])
def test_batch_excluded_fifo_is_not_reported(tmp_path, fifo, regular, source):
    args = ["batch", "-l", "python", "--json", "-q", "--exclude", "*/input.py"]
    if source == "stdin":
        result = _run(*args, "--stdin", cwd=tmp_path, stdin=f"{fifo}\n{regular}\n")
    else:
        result = _run(*args, str(fifo), str(regular), cwd=tmp_path)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert MESSAGE not in result.stderr
    assert {c["file_path"] for c in json.loads(result.stdout)} == {str(regular)}


def test_non_regular_file_error_pickle_round_trip(tmp_path):
    error = NonRegularFileError(tmp_path / "pipe.py", "FIFO/named pipe")
    restored = pickle.loads(pickle.dumps(error))
    assert type(restored) is NonRegularFileError
    assert restored.path == error.path
    assert restored.kind == error.kind
    assert str(restored) == str(error)


def test_chunk_files_parallel_keeps_results_beside_directory(tmp_path, regular):
    # A worker's NonRegularFileError must cross the process boundary as an
    # ordinary per-file failure, not break the pool for the whole batch.
    other = tmp_path / "other.py"
    other.write_bytes(regular.read_bytes())
    directory = tmp_path / "pkg.py"
    directory.mkdir()
    chunker = ParallelChunker("python", num_workers=2, use_cache=False)
    results = chunker.chunk_files_parallel([directory, regular, other])
    assert results[directory] == []
    assert results[regular]
    assert results[other]


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
    assert DIRECTORY_GUIDANCE in str(excinfo.value)


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
