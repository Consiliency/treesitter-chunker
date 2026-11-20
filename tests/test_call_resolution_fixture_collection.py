"""Tool exclusions for the call-resolution fixtures (treesitter-chunker#682, PR 0).

The fixture trees under ``tests/fixtures/call_resolution`` are byte-pinned
inputs. Some contain ``test_*.py`` files of their own (Greenfield's
``r9-py/tests/test_svc.py``), and none follow the repository's lint rules. So
pytest, Black and Ruff must skip them, Git must never rewrite their line
endings, and the sdist must still ship them (plan section 10.1).
"""

from __future__ import annotations

import fnmatch
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = "tests/fixtures/call_resolution"
FIXTURES = ROOT / FIXTURE_DIR
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
MANIFEST_IN_LINE = f"recursive-include {FIXTURE_DIR} *"


def test_fixture_trees_contain_collectable_test_modules() -> None:
    """The pytest exclusion is load-bearing: a fixture tree has a test module."""
    assert (FIXTURES / "greenfield-r1/r9-py/tests/test_svc.py").is_file()


def test_pytest_addopts_ignore_the_fixture_directory() -> None:
    addopts = PYPROJECT["tool"]["pytest"]["ini_options"]["addopts"]
    assert f"--ignore={FIXTURE_DIR}" in addopts


def test_collecting_tests_fixtures_yields_no_tests() -> None:
    """``pytest --collect-only tests/fixtures`` collects nothing at all."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "tests/fixtures",
        ],
        capture_output=True,
        check=False,
        cwd=ROOT,
        text=True,
        timeout=120,
    )
    output = result.stdout + result.stderr
    # Exit code 5 is pytest's "no tests were collected".
    assert result.returncode == 5, output
    assert "no tests collected" in output, output
    assert "test_svc" not in output, output


def test_black_excludes_the_fixture_directory() -> None:
    pattern = PYPROJECT["tool"]["black"]["extend-exclude"]
    regex = re.compile(pattern, re.VERBOSE)
    assert regex.search(f"/{FIXTURE_DIR}/greenfield-r1/r9-py/tests/test_svc.py")
    # The exclusion is scoped: other fixtures and tests stay formatted.
    assert not regex.search("/tests/fixtures/boundary_ir/repos/python/app.py")
    assert not regex.search("/tests/test_call_resolution_fixture_collection.py")


def test_ruff_excludes_the_fixture_directory() -> None:
    # extend-exclude, because the CI command's --exclude flags replace the
    # exclude list. tests/test_lint_path_policy.py runs that command.
    assert FIXTURE_DIR in PYPROJECT["tool"]["ruff"]["extend-exclude"]


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
def test_gitattributes_keep_fixture_bytes() -> None:
    lines = (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()
    assert f"{FIXTURE_DIR}/** -text" in lines
    if not (ROOT / ".git").exists():
        pytest.skip("not a Git checkout")
    samples = [
        f"{FIXTURE_DIR}/greenfield-r1/r9-ts/web/svc.ts",
        f"{FIXTURE_DIR}/off_mode_baseline/MANIFEST.sha256",
        f"{FIXTURE_DIR}/expected/r9-ts.json",
    ]
    result = subprocess.run(
        ["git", "check-attr", "text", "--", *samples],
        capture_output=True,
        check=True,
        cwd=ROOT,
        text=True,
        timeout=60,
    )
    assert result.stdout.splitlines() == [f"{path}: text: unset" for path in samples]


def _manifest_in_patterns() -> list[list[str]]:
    patterns = []
    for line in (ROOT / "MANIFEST.in").read_text(encoding="utf-8").splitlines():
        words = line.split()
        if words[:1] == ["recursive-include"] and len(words) > 2:
            directory = words[1].rstrip("/")
            if directory == FIXTURE_DIR or FIXTURE_DIR.startswith(f"{directory}/"):
                patterns.append(words[2:])
    return patterns


def test_manifest_in_ships_every_fixture_file() -> None:
    """The sdist keeps every fixture extension (.ts, .tsx, .kt, .cs, .json, ...)."""
    lines = (ROOT / "MANIFEST.in").read_text(encoding="utf-8").splitlines()
    assert MANIFEST_IN_LINE in lines
    patterns = [pattern for group in _manifest_in_patterns() for pattern in group]
    names = {path.name for path in FIXTURES.rglob("*") if path.is_file()}
    uncovered = sorted(
        name
        for name in names
        if not any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)
    )
    assert uncovered == []
    extensions = {Path(name).suffix for name in names}
    assert {".ts", ".tsx", ".kt", ".cs", ".json", ".sha256", ".md"} <= extensions
