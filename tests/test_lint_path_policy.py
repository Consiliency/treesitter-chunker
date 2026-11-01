"""Canonical lint/format path list and Ruff inclusion policy (IF-0-CIFAST-1).

treesitter-chunker#517: recursive Ruff discovery skipped the tracked
``chunker/build`` sources. The repository ``.gitignore`` entry ``build/`` and
the ``[tool.ruff]`` ``exclude`` entry ``"build"`` both match any directory named
``build``, so ``ruff check chunker/`` never saw ``chunker/build/*.py``.

The policy keeps both exclusions for generated build output and lists the
tracked source package ``chunker/build/`` explicitly. Ruff does not apply its
exclusions to a path named on the command line (``force-exclude`` is unset).
CI, release validation, CONTRIBUTING.md and the release checklist must run
exactly these commands.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UV_PREFIX = "uv run --locked --all-extras"

GOVERNED_TOOLS = (
    "tools/governed_group.py",
    "tools/governed_scope.py",
    "tools/sync_governed_test_transport.py",
)
RUFF_PATHS = ("chunker/", "chunker/build/", "cli/", "tests/", *GOVERNED_TOOLS)
RUFF_ARGS = (
    *RUFF_PATHS,
    "--exclude",
    "archive",
    "--exclude",
    "logs",
    "--exclude",
    "site",
)
BLACK_PATHS = ("chunker/", "cli/", "tests/", "scripts/", *GOVERNED_TOOLS)

CANONICAL_RUFF = f"{UV_PREFIX} ruff check {' '.join(RUFF_ARGS)}"
CANONICAL_BLACK = f"{UV_PREFIX} black --check {' '.join(BLACK_PATHS)}"

COMMAND_FILES = (
    ".github/workflows/ci.yml",
    ".github/workflows/release.yml",
    "CONTRIBUTING.md",
    "docs/development/RELEASE_CHECKLIST.md",
)

# A deliberate violation: Ruff F401 (unused import) at the appended line.
PROBE_IMPORT = "import json as _lint_probe_unused\n"


def _command_lines(relative: str, tool: str) -> list[str]:
    text = (ROOT / relative).read_text(encoding="utf-8")
    marker = f"{UV_PREFIX} {tool} "
    return [
        # Markdown lists wrap commands in inline code; drop the backticks.
        line[line.index(marker) :].strip().rstrip("`")
        for line in text.splitlines()
        if marker in line
    ]


@pytest.mark.parametrize("relative", COMMAND_FILES)
def test_lint_and_format_commands_match_canonical_list(relative: str) -> None:
    """Every documented or automated lint/format command uses IF-0-CIFAST-1."""
    assert _command_lines(relative, "ruff check") == [CANONICAL_RUFF]
    assert _command_lines(relative, "black --check") == [CANONICAL_BLACK]


def _ruff(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "ruff", *args],
        capture_output=True,
        check=False,
        cwd=cwd,
        text=True,
        timeout=120,
    )


def _tracked(*pathspecs: str, cwd: Path = ROOT) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", *pathspecs],
        capture_output=True,
        check=True,
        cwd=cwd,
        timeout=60,
    )
    return [item for item in result.stdout.decode("utf-8").split("\0") if item]


def test_every_tracked_python_source_under_listed_roots_reaches_ruff() -> None:
    """The canonical Ruff command discovers each tracked file it is meant to see."""
    roots = [path.rstrip("/") for path in RUFF_PATHS if path.endswith("/")]
    tracked = {path for path in _tracked(*roots) if path.endswith((".py", ".pyi"))}
    assert {
        path for path in tracked if path.startswith("chunker/build/")
    }, "expected tracked chunker/build sources"

    result = _ruff("check", "--show-files", *RUFF_ARGS, cwd=ROOT)
    assert result.returncode == 0, result.stderr
    shown = {
        Path(line).resolve().relative_to(ROOT).as_posix()
        for line in result.stdout.splitlines()
        if line.strip()
    }
    assert sorted(tracked - shown) == []


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], check=True, cwd=root, capture_output=True, timeout=60
    )


def _probe_repository(root: Path) -> None:
    """Build a disposable Git checkout holding the inputs of the CI command."""
    for name in ("pyproject.toml", ".gitignore"):
        shutil.copy2(ROOT / name, root / name)
    for relative in [
        *_tracked("chunker/build"),
        *GOVERNED_TOOLS,
        *_tracked("tools/__init__.py"),
    ]:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    for directory in ("cli", "tests"):
        (root / directory).mkdir(exist_ok=True)
    # Generated build output stays excluded: this untracked, ignored file has a
    # violation that the canonical command must not report.
    generated = root / "build" / "lib" / "generated.py"
    generated.parent.mkdir(parents=True)
    generated.write_text(PROBE_IMPORT, encoding="utf-8")

    _git(root, "init", "-q")
    _git(root, "add", "-A")
    # chunker/build matches the ignored ``build/`` pattern; like the real
    # repository, its sources are tracked explicitly.
    _git(root, "add", "--force", "chunker/build")


def _diagnostics(root: Path) -> tuple[int, list[tuple[str, str, int]]]:
    result = _ruff("check", "--output-format", "json", *RUFF_ARGS, cwd=root)
    assert result.returncode in (0, 1), result.stderr
    found = [
        (
            Path(item["filename"]).resolve().relative_to(root.resolve()).as_posix(),
            item["code"],
            item["location"]["row"],
        )
        for item in json.loads(result.stdout or "[]")
    ]
    return result.returncode, sorted(found)


def test_violation_in_tracked_build_module_fails_ci_ruff(tmp_path: Path) -> None:
    """A deliberate F401 in tracked ``chunker/build`` fails the CI Ruff command."""
    root = tmp_path / "repo"
    root.mkdir()
    _probe_repository(root)
    tracked = _tracked(cwd=root)
    assert "chunker/build/builder.py" in tracked
    assert "build/lib/generated.py" not in tracked

    # Control: the tracked build sources are clean under the canonical command.
    assert _diagnostics(root) == (0, [])

    target = root / "chunker" / "build" / "builder.py"
    original = target.read_text(encoding="utf-8")
    target.write_text(original + PROBE_IMPORT, encoding="utf-8")
    probe_row = original.count("\n") + 1
    _git(root, "add", "--force", "chunker/build/builder.py")

    returncode, found = _diagnostics(root)
    assert returncode == 1
    assert ("chunker/build/builder.py", "F401", probe_row) in found
    # Only the probe line is reported (placement rules such as E305 may also
    # fire on it); nothing else in the checkout, including build/, is.
    assert {(path, row) for path, _code, row in found} == {
        ("chunker/build/builder.py", probe_row)
    }
