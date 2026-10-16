#!/usr/bin/env python3
"""Run the standing GitHub CI smoke pytest batch."""

from __future__ import annotations

import subprocess
import sys


CI_SMOKE_TESTS = [
    "tests/test_auto.py",
    "tests/test_chunking.py",
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
    "tests/test_supported_wheel_verification.py",
    "tests/test_sqlite_export_contract.py",
    "tests/test_platform_support_contract.py",
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
    # The 0.13.0 pack's COBOL grammar previously infinite-looped inside native
    # code, beyond pytest-timeout's signal interrupt. The 1.20 gate therefore
    # includes an OS-subprocess probe that is killed and reaped at its deadline.
    # See .github/workflows/ci.yml for the exact pack install and prefetch.
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
