#!/usr/bin/env python3
"""Run the standing cross-platform core pytest batch."""

from __future__ import annotations

import argparse
import subprocess
import sys


COMMON_TESTS = [
    "tests/test_grammar_integrity.py::test_download_archive_handle_lifetime",
    "tests/test_grammar_management.py::test_real_grammar_mtimes_do_not_invent_compilation_dates",
    "tests/test_streaming.py::TestBufferOptimization::test_repeated_streaming_preserves_eager_fixture_chunks",
    "tests/test_config.py",
    "tests/test_env_config.py",
    "tests/test_config_advanced_scenarios.py",
    "tests/test_cli.py",
    "tests/test_node_explorer_contract.py",
    "tests/test_debug_repl_contract.py",
    "tests/test_public_grammar_validator.py",
    "tests/test_grammar_self_test_workflow.py",
    "tests/test_core_grammar_cache_cleanup.py",
    "tests/test_grammar_installer_language_safety.py",
    "tests/test_public_grammar_registry.py",
    "tests/test_public_grammar_cli.py",
    "tests/test_public_grammar_config.py",
    "tests/test_grammar_candidate_compatibility.py",
    "tests/test_grammar_compatibility_contract.py",
    "tests/test_compatibility_database_reload.py",
    "tests/test_language_compatibility_records_contract.py",
    "tests/test_compatibility_schema_json_contract.py",
    "tests/test_compatibility_schema_version_boundaries.py",
    "tests/test_compiled_grammar_analysis_contract.py",
    "tests/test_git_aware_linked_worktree.py",
    "tests/test_git_aware_contract.py",
    "tests/test_python_version_hints_contract.py",
    "tests/test_javascript_version_hints_contract.py",
    "tests/test_rust_version_hints_contract.py",
    "tests/test_go_version_hints_contract.py",
    "tests/test_java_version_hints_contract.py",
    "tests/test_cpp_version_hints_contract.py",
    "tests/test_graphml_yed_export_contract.py",
    "tests/test_sqlite_export_contract.py",
    "tests/test_platform_support_contract.py",
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
