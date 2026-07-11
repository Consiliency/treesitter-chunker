#!/usr/bin/env python3
"""Baseline-relative mypy gate (GATES phase).

The codebase carries ~2.2k pre-existing strict-mypy errors (a hidden type-debt
surfaced when GATES removed the CI `::warning::` downgrade). Failing CI on all of
them would leave the pipeline permanently red and block every PR — honest but
useless. Instead this gate:

  * runs strict mypy,
  * normalizes each error to a line-number-independent signature (path + message),
  * fails ONLY on signatures absent from `docs/development/mypy-baseline.txt`.

So new type errors are blocked immediately while the tracked debt is paid down by
shrinking the baseline over time. Regenerate the baseline intentionally with
`--update` after a legitimate reduction.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

BASELINE = Path(__file__).resolve().parents[1] / "docs" / "development" / "mypy-baseline.txt"
MYPY_CMD = [
    "mypy",
    "chunker/",
    "cli/",
    "--ignore-missing-imports",
    "--no-error-summary",
    "--no-color-output",
]
_LINECOL = re.compile(r":\d+:\d+:")
_LINE = re.compile(r":\d+:")


def _signature(line: str) -> str:
    """Strip line/column numbers so a signature is stable across unrelated edits."""
    return _LINE.sub(":", _LINECOL.sub(":", line)).strip()


def _run_mypy() -> list[str]:
    proc = subprocess.run(MYPY_CMD, capture_output=True, text=True)
    return [ln for ln in proc.stdout.splitlines() if " error:" in ln]


def main(argv: list[str]) -> int:
    current = {_signature(ln) for ln in _run_mypy()}
    if "--update" in argv:
        BASELINE.write_text("\n".join(sorted(current)) + "\n", encoding="utf-8")
        print(f"mypy baseline updated: {len(current)} signatures")
        return 0
    baseline = {
        ln.strip()
        for ln in BASELINE.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    }
    new_errors = sorted(current - baseline)
    if new_errors:
        print("NEW mypy errors not in baseline (fix these):", file=sys.stderr)
        for e in new_errors:
            print(f"  {e}", file=sys.stderr)
        print(
            f"\n{len(new_errors)} new error signature(s); "
            f"baseline holds {len(baseline)} tracked-debt signatures.",
            file=sys.stderr,
        )
        return 1
    fixed = len(baseline) - len(current & baseline)
    print(
        f"mypy gate OK: no new errors. Tracked debt: {len(current & baseline)}"
        + (f" ({fixed} baseline signatures newly cleared — run --update)" if fixed else ""),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
