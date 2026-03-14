#!/usr/bin/env python3
"""Run the standing Windows preflight pytest batch."""

from __future__ import annotations

import subprocess
import sys


WINDOWS_PREFLIGHT_TESTS = [
    "tests/test_env_config.py",
    "tests/test_config_advanced_scenarios.py",
    "tests/test_exceptions.py",
    "tests/test_extraction_framework.py",
    "tests/test_export_integration_advanced.py",
    "tests/test_fallback_chunking.py",
    "tests/test_registry_fallback.py",
    "tests/test_config.py",
    "tests/test_cli.py",
]


def main() -> int:
    cmd = [sys.executable, "-m", "pytest", "-q", *WINDOWS_PREFLIGHT_TESTS]
    print("Running Windows preflight batch:")
    for test in WINDOWS_PREFLIGHT_TESTS:
        print(f"- {test}")
    return subprocess.run(cmd, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
