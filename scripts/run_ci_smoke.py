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
