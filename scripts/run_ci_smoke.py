#!/usr/bin/env python3
"""Run the standing GitHub CI smoke pytest batch."""

from __future__ import annotations

import subprocess
import sys


CI_SMOKE_TESTS = [
    "tests/test_auto.py",
    "tests/test_chunking.py",
    "tests/test_cli.py",
    "tests/test_env_config.py",
    "tests/test_config.py",
    "tests/test_factory.py",
    "tests/test_registry_fallback.py",
    "tests/test_fallback_chunking.py",
    "tests/test_boundary_ir_golden_snapshots.py",
    "tests/test_boundary_ir_incremental_benchmark.py",
    "tests/test_canon_vectors.py",
    # Blocking determinism + parity + schema gates (P0/P1/P2). These guard the
    # Boundary-IR contract spec consumers hash against; they must be honestly
    # green in CI, not just present in the tree.
    "tests/test_boundary_determinism.py",
    "tests/test_boundary_parity_view.py",
    "tests/test_boundary_ir_schema.py",
    # Determinism gate: per-language golden non-empty guard + fail-closed
    # grammar/runtime pin assertion (the silent-{} and ABI-drift failure modes).
    "tests/test_boundary_ir_determinism.py",
    "tests/test_pack_pin_drift.py",
    # Smoke-tier coverage gate: comprehensive LOAD smoke across the ENTIRE pack
    # (every grammar must load under the pin -- forward ABI-drift tripwire) plus
    # per-language coverage diffed against the committed docs/language-coverage
    # .json oracle. Complements the deep 12-language golden gate above.
    #
    # Re-landed (previously reverted in #84) now that the CI install pins the pack
    # to ==0.9.0. The 60-min Pytest hang was NOT the test logic or the
    # built-grammar-lib path: `uv pip install` ignores uv.lock, so the pack
    # floated to 0.13.0, whose `cobol` grammar infinite-loops in parser.parse() at
    # the C level -- and pytest-timeout's signal-based interrupt cannot kill a C
    # loop, so the load smoke hung the whole step. Under the pinned 0.9.0 (the
    # byte-stable, ABI-paired env this gate is baked against) cobol is not even a
    # pack grammar; the full batch runs in seconds. See .github/workflows/ci.yml.
    "tests/test_language_smoke.py",
]


def main() -> int:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-n",
        "auto",
        "--timeout=60",
        "-q",
        *CI_SMOKE_TESTS,
    ]
    print("Running CI smoke batch:")
    for test in CI_SMOKE_TESTS:
        print(f"- {test}")
    return subprocess.run(cmd, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
