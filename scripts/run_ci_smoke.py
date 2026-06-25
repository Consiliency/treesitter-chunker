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
    # Blocking determinism + parity + schema gates (P0/P1/P2). These guard the
    # Boundary-IR contract spec consumers hash against; they must be honestly
    # green in CI, not just present in the tree.
    "tests/test_boundary_determinism.py",
    "tests/test_boundary_parity_view.py",
    "tests/test_boundary_ir_schema.py",
    # Determinism gate: per-language golden non-empty guard + fail-closed
    # grammar/runtime pin assertion (the silent-{} and ABI-drift failure modes).
    "tests/test_boundary_ir_determinism.py",
    # Smoke-tier coverage gate (tests/test_language_smoke.py): TEMPORARILY removed
    # from the standing CI batch -- it blew the 60-min Pytest step on a fresh CI
    # runner (the built-grammar-lib extraction path, not the test logic, which is
    # ~0.3s via the pack). The test file + docs/language-coverage.{md,json} oracle
    # remain committed and runnable locally; it will be re-added once the CI perf
    # fix lands (branch fix/smoke-gate-ci-timeout). Reverted-to-green per the
    # revert-then-fix-forward discipline; the gate's VALUE is preserved, only its
    # CI wiring is paused.
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
