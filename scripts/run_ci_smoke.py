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
