"""The fork-terminal skill quotes TMPDIR-based paths in shell commands (treesitter-chunker#481).

Its output and done-marker files live under the inherited ``TMPDIR``. A
``TMPDIR`` may contain spaces or shell metacharacters, so every path that goes
into a POSIX shell command must be quoted. The command builder is exercised
with real ``bash``; no terminal is launched.
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / ".ai-dev-kit/skills/spawn/agent/fork_terminal.py"

pytestmark = pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("bash") is None,
    reason="POSIX shell command builder",
)


@pytest.fixture(scope="module")
def fork_terminal():
    spec = importlib.util.spec_from_file_location("fork_terminal_skill", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def awkward_tmpdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    scratch = tmp_path / "scratch with spaces; $(not run) 'q'"
    scratch.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(scratch))
    return scratch


def _run(command: str, cwd: Path) -> None:
    subprocess.run(["bash", "-c", command], cwd=cwd, check=True, timeout=30)


@pytest.mark.parametrize("mode", ["agent", "debug"])
def test_capture_command_writes_exactly_the_returned_paths(
    fork_terminal, awkward_tmpdir: Path, tmp_path: Path, mode: str
) -> None:
    agent, debug, done = fork_terminal._output_paths(
        "abc12345", mode == "agent", mode == "debug"
    )
    output = agent if mode == "agent" else debug
    assert Path(output).parent == awkward_tmpdir
    assert Path(done).parent == awkward_tmpdir

    workdir = tmp_path / "work"
    workdir.mkdir()
    command = "printf 'hello\\n'" if mode == "agent" else "{ printf 'oops\\n' >&2; }"
    _run(fork_terminal._posix_capture_command(command, agent, debug, done), workdir)

    expected = "hello\n" if mode == "agent" else "oops\n"
    assert Path(output).read_text(encoding="utf-8") == expected
    assert Path(done).exists()
    # Nothing was split into stray files, and the command substitution in the
    # directory name never ran.
    assert sorted(path.name for path in awkward_tmpdir.iterdir()) == sorted(
        [Path(output).name, Path(done).name]
    )
    assert list(workdir.iterdir()) == []
    assert sorted(path.name for path in tmp_path.iterdir()) == sorted(
        [awkward_tmpdir.name, "work"]
    )


def test_no_capture_leaves_the_command_unwrapped(fork_terminal) -> None:
    assert fork_terminal._posix_capture_command("true", None, None, "done") is None


def test_applescript_string_escapes_quotes_and_backslashes(fork_terminal) -> None:
    text = "cd '/a b'; printf \"x\\\\y\" | tee '/c \"d\"'"
    literal = fork_terminal._applescript_string(text)
    assert literal.startswith('"') and literal.endswith('"')
    body = literal[1:-1]
    # No bare quote ends the literal early; decoding restores the command.
    assert '"' not in re.sub(r"\\.", "", body)
    assert re.sub(r"\\(.)", r"\1", body) == text
