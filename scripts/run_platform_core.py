#!/usr/bin/env python3
"""Run the standing cross-platform core pytest batch."""

from __future__ import annotations

import argparse
import subprocess
import sys


COMMON_TESTS = [
    "tests/test_config.py",
    "tests/test_env_config.py",
    "tests/test_config_advanced_scenarios.py",
    "tests/test_cli.py",
    "tests/test_exceptions.py",
    "tests/test_fallback_chunking.py",
    "tests/test_registry_fallback.py",
]

WINDOWS_EXTRA_TESTS = [
    "tests/test_export_integration_advanced.py",
]

MACOS_EXTRA_TESTS = [
    "tests/test_export_integration_advanced.py",
]

LINUX_EXTRA_TESTS = [
    "tests/test_factory.py",
]


def tests_for_platform(platform: str) -> list[str]:
    tests = list(COMMON_TESTS)
    if platform == "windows":
        tests.extend(WINDOWS_EXTRA_TESTS)
    elif platform == "macos":
        tests.extend(MACOS_EXTRA_TESTS)
    elif platform == "linux":
        tests.extend(LINUX_EXTRA_TESTS)
    else:
        raise ValueError(f"Unsupported platform: {platform}")
    return tests


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--platform",
        required=True,
        choices=["linux", "windows", "macos"],
        help="Platform suite to run",
    )
    args = parser.parse_args()

    tests = tests_for_platform(args.platform)
    cmd = [sys.executable, "-m", "pytest", "-xq", *tests]
    if args.platform == "linux":
        cmd += ["--cov=chunker", "--cov-report=xml"]
    print(f"Running platform core batch for {args.platform}:")
    for test in tests:
        print(f"- {test}")
    return subprocess.run(cmd, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
