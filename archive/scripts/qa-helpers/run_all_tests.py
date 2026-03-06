#!/usr/bin/env python3
"""Run all tests including unit tests, integration tests, and example validation."""

import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list, description: str) -> bool:
    """Run a command and return success status."""
    print(f"\n🚀 {description}")
    print("=" * 50)

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        if result.stdout.strip():
            print("Output:", result.stdout.strip())
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed")
        print(f"Error: {e}")
        if e.stdout.strip():
            print("Stdout:", e.stdout.strip())
        if e.stderr.strip():
            print("Stderr:", e.stderr.strip())
        return False


def main():
    """Run all tests."""
    project_root = Path(__file__).parent.parent

    print("�� COMPREHENSIVE TEST SUITE")
    print("=" * 40)

    # Change to project root
    os.chdir(project_root)

    # Test sequence
    tests = [
        (["python", "-m", "pytest", "tests/", "-v"], "Unit Tests"),
        (["python", "-m", "pytest", "tests/integration/", "-v"], "Integration Tests"),
        (["python", "scripts/validate_examples.py"], "Example Validation"),
        (
            ["python", "-m", "flake8", "chunker/", "--max-line-length=100"],
            "Code Quality (Flake8)",
        ),
        (
            ["python", "-m", "mypy", "chunker/", "--ignore-missing-imports"],
            "Type Checking (MyPy)",
        ),
    ]

    results = []
    for cmd, desc in tests:
        success = run_command(cmd, desc)
        results.append((desc, success))

    # Summary
    print("\n�� TEST SUMMARY")
    print("=" * 30)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for desc, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {desc}")

    print(f"\n🎯 Overall: {passed}/{total} test suites passed")

    if passed == total:
        print("🎉 All tests passed! Ready for deployment!")
        return 0
    print("⚠️  Some tests failed. Please fix issues before deployment.")
    return 1


if __name__ == "__main__":
    main()
