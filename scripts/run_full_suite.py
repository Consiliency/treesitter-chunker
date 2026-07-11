#!/usr/bin/env python3
"""Run the nightly full test tier, including the specification tests."""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    cmd = [sys.executable, "-m", "pytest", "-q", "tests", "spec_tests"]
    print("Running nightly full suite: tests and spec_tests")
    return subprocess.run(cmd, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
