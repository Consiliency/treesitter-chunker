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
import sys
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


def _assert_committed_form(data: bytes) -> None:
    """Sorted, unique, LF-terminated signature lines; empty when debt is zero."""
    text = data.decode("utf-8")
    assert "\r" not in text
    assert text == "" or text.endswith("\n")
    lines = text.splitlines()
    assert lines == sorted(set(lines))
    assert all(line.strip() == line and line for line in lines)


def test_committed_baseline_is_sorted_and_unique() -> None:
    _assert_committed_form(
        (ROOT / "docs" / "development" / "mypy-baseline.txt").read_bytes()
    )


def test_update_clearing_the_last_signature_leaves_an_empty_file(
    gate: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    _report(gate, monkeypatch)
    assert gate.main(["--update"]) == 0
    assert gate.BASELINE.read_bytes() == b""
    _assert_committed_form(gate.BASELINE.read_bytes())


def test_update_of_an_empty_baseline_stays_empty(
    gate: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate.BASELINE.write_bytes(b"")
    _report(gate, monkeypatch)
    assert gate.main(["--update"]) == 0
    assert gate.BASELINE.read_bytes() == b""
    _report(gate, monkeypatch, NEW)
    assert gate.main(["--update"]) == 1
    assert gate.BASELINE.read_bytes() == b""


def test_update_writes_lf_terminated_sorted_lines(
    gate: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    _report(gate, monkeypatch, CLEARED, OLD)
    assert gate.main(["--update"]) == 0
    expected = sorted(gate._signature(line) for line in (OLD, CLEARED))
    assert gate.BASELINE.read_bytes() == "".join(f"{s}\n" for s in expected).encode(
        "utf-8"
    )
    _assert_committed_form(gate.BASELINE.read_bytes())


def _command_lines(relative: str, marker: str) -> list[str]:
    """Whole stripped lines naming the command.

    Markdown list items lose their ``- `` marker and inline-code backticks.
    Nothing else is removed, so a commented-out or prefixed command no longer
    equals the canonical text.
    """
    text = (ROOT / relative).read_text(encoding="utf-8")
    return [
        line.strip().removeprefix("- ").strip("`")
        for line in text.splitlines()
        if marker in line
    ]


def test_command_lines_reject_commented_or_prefixed_commands(tmp_path, monkeypatch):
    sample = tmp_path / "sample.yml"
    sample.write_text(
        f"        {CANONICAL_GATE}\n"
        f"#        {CANONICAL_GATE}\n"
        f"        {CANONICAL_GATE} || true\n"
        f"- `{CANONICAL_GATE}`\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys.modules[__name__], "ROOT", tmp_path)
    assert _command_lines("sample.yml", CANONICAL_GATE) == [
        CANONICAL_GATE,
        f"#        {CANONICAL_GATE}",
        f"{CANONICAL_GATE} || true",
        CANONICAL_GATE,
    ]


@pytest.mark.parametrize("relative", COMMAND_FILES)
def test_type_commands_match_ci(relative: str) -> None:
    """CI, release validation and the documented checks run both type commands."""
    assert _command_lines(relative, f"{UV_PREFIX} python scripts/mypy_gate.py") == [
        CANONICAL_GATE
    ]
    assert _command_lines(relative, f"{UV_PREFIX} mypy ") == [CANONICAL_GOVERNED]
