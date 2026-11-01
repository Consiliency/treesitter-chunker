"""Type-gate policy: shrink-only baseline and aligned type commands.

treesitter-chunker#587:

* ``scripts/mypy_gate.py --update`` used to write every current signature to
  the baseline, so one command absorbed new errors. ``--update`` now only
  removes cleared signatures. If mypy reports a signature absent from the
  baseline, it fails and leaves the file byte-for-byte unchanged.
* ``release.yml`` release validation skipped the governed-tools body-type
  check that CI runs. CI, release validation, CONTRIBUTING.md and the release
  checklist must run the same two type commands.

The gate tests replace only ``_run_mypy`` (the subprocess call) with fixed
mypy output lines; signature normalization, comparison and baseline writing are
the real code.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
UV_PREFIX = "uv run --locked --all-extras"

CANONICAL_GATE = f"{UV_PREFIX} python scripts/mypy_gate.py"
CANONICAL_GOVERNED = (
    f"{UV_PREFIX} mypy --follow-imports=silent --allow-untyped-defs"
    " --allow-incomplete-defs --allow-untyped-calls --check-untyped-defs"
    " --no-pretty --no-error-summary --show-error-codes"
    " tools/sync_governed_test_transport.py"
)

COMMAND_FILES = (
    ".github/workflows/ci.yml",
    ".github/workflows/release.yml",
    "CONTRIBUTING.md",
    "docs/development/RELEASE_CHECKLIST.md",
)

OLD = "chunker/a.py:10:5: error: Old debt  [misc]"
CLEARED = "chunker/b.py:3: error: Cleared debt  [misc]"
NEW = "chunker/c.py:7:1: error: Candidate error  [return-value]"


def _load_gate() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "mypy_gate_under_test", ROOT / "scripts" / "mypy_gate.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    module = _load_gate()
    baseline = tmp_path / "mypy-baseline.txt"
    signatures = sorted(module._signature(line) for line in (OLD, CLEARED))
    baseline.write_text("\n".join(signatures) + "\n", encoding="utf-8")
    monkeypatch.setattr(module, "BASELINE", baseline)
    return module


def _report(module: ModuleType, monkeypatch: pytest.MonkeyPatch, *lines: str):
    monkeypatch.setattr(module, "_run_mypy", lambda: list(lines))


def test_update_refuses_to_absorb_new_signature(
    gate: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    before = gate.BASELINE.read_bytes()
    _report(gate, monkeypatch, OLD, NEW)

    assert gate.main(["--update"]) == 1

    assert gate.BASELINE.read_bytes() == before
    err = capsys.readouterr().err
    assert gate._signature(NEW) in err
    assert "Baseline not updated" in err


def test_update_removes_only_cleared_signatures(
    gate: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    _report(gate, monkeypatch, OLD, OLD.replace(":10:5:", ":99:1:"))

    assert gate.main(["--update"]) == 0

    assert gate.BASELINE.read_text(encoding="utf-8") == gate._signature(OLD) + "\n"


def test_check_fails_on_new_signature_and_passes_on_subset(
    gate: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = gate.BASELINE.read_bytes()
    _report(gate, monkeypatch, OLD, NEW)
    assert gate.main([]) == 1
    _report(gate, monkeypatch, OLD)
    assert gate.main([]) == 0
    assert gate.BASELINE.read_bytes() == before


def test_committed_baseline_is_sorted_and_unique() -> None:
    lines = (
        (ROOT / "docs" / "development" / "mypy-baseline.txt")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert lines == sorted(set(lines))
    assert all(line.strip() == line and line for line in lines)


def _command_lines(relative: str, marker: str) -> list[str]:
    text = (ROOT / relative).read_text(encoding="utf-8")
    return [
        # Markdown lists wrap commands in inline code; drop the backticks.
        line[line.index(marker) :].strip().rstrip("`")
        for line in text.splitlines()
        if marker in line
    ]


@pytest.mark.parametrize("relative", COMMAND_FILES)
def test_type_commands_match_ci(relative: str) -> None:
    """CI, release validation and the documented checks run both type commands."""
    assert _command_lines(relative, f"{UV_PREFIX} python scripts/mypy_gate.py") == [
        CANONICAL_GATE
    ]
    assert _command_lines(relative, f"{UV_PREFIX} mypy ") == [CANONICAL_GOVERNED]
