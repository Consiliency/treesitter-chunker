"""Run serial, temporary #630 mutations on their designated hosted platform.

Every source edit is restored in finally. A pytest assertion failure is evidence;
a collection/import error, interruption, or passing mutant is not a kill.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RECIPE = "chunker/grammar_management/_build_recipe.py"
CORE = "chunker/grammar_management/core.py"
CLI = "chunker/grammar_management/cli.py"
BUILDER = "chunker/grammar/builder.py"
MANAGER = "chunker/grammar_manager.py"
PLATFORM = "chunker/build/builder.py"
TOOLS = "chunker/grammar_management/_build_tools.py"
DIGEST = "tests/test_reproducible_grammar_build.py"
CONTRACT = "tests/test_remaining_builder_contract.py"
# name, path, old text, replacement, pytest selector
MUTATIONS: list[tuple[str, str, str, str, str]] = []


def add(name: str, path: str, old: str, new: str, test: str) -> None:
    MUTATIONS.append((name, path, old, new, test))


if sys.platform.startswith("linux"):
    add(
        "drop_z_defs",
        RECIPE,
        'return ["-Wl,-z,defs"]',
        "return []",
        DIGEST + "::test_gcc_route_refuses_undefined_symbols",
    )
    add(
        "wheel_unstable_language_selection",
        PLATFORM,
        "sorted(available)[:3]",
        "list(available)[:3]",
        CONTRACT + "::test_wheel_language_selection_is_sorted",
    )
    for prefix, path in (("manager", MANAGER), ("combined", BUILDER)):
        key = "languages_to_compile" if prefix == "manager" else "languages"
        add(
            prefix + "_left_out_reported_true",
            path,
            f"results = dict.fromkeys({key}, False)",
            f"results = dict.fromkeys({key}, True)",
            CONTRACT + f"::test_combined_membership[cc-{prefix}]",
        )
        add(
            prefix + "_member_failure_fails_all",
            path,
            "if not accepted:",
            "if errors or not accepted:",
            CONTRACT + f"::test_combined_membership[cc-{prefix}]",
        )
        old = (
            "if completed.returncode == 0 and self._lib_path.is_file():"
            if prefix == "manager"
            else "success = result.returncode == 0 and lib_path.is_file()"
        )
        new = "if True:" if prefix == "manager" else "success = True"
        add(
            prefix + "_link_failure_partial_true",
            path,
            old,
            new,
            CONTRACT + f"::test_combined_link_failure_fails_all[{prefix}]",
        )
    add(
        "platform_left_out_reported_true",
        PLATFORM,
        'build_info["errors"].extend(',
        "list(",
        CONTRACT + "::test_combined_membership[cc-platform]",
    )
    add(
        "platform_member_failure_fails_all",
        PLATFORM,
        "if not accepted:",
        "if errors or not accepted:",
        CONTRACT + "::test_combined_membership[cc-platform]",
    )
    add(
        "platform_link_failure_partial_true",
        PLATFORM,
        "if result.returncode == 0 and lib_path.is_file():",
        "if True:",
        CONTRACT + "::test_combined_link_failure_fails_all[platform]",
    )
    add(
        "manager_unsorted_sources",
        RECIPE,
        "sorted(set(sources)), sorted(includes)",
        "list(reversed(sorted(set(sources)))), sorted(includes)",
        CONTRACT + "::test_combined_source_and_include_order",
    )
    add(
        "platform_unsorted_includes",
        RECIPE,
        "sorted(set(sources)), sorted(includes)",
        "sorted(set(sources)), list(reversed(sorted(includes)))",
        CONTRACT + "::test_combined_source_and_include_order",
    )
    add(
        "individual_wrong_subdir",
        BUILDER,
        "cwd=lang_root.absolute(),",
        "cwd=self._source_dir.absolute(),",
        DIGEST + "::test_remaining_public_adapters_two_paths[individual-mapped]",
    )
    add(
        "cli_wrong_cwd",
        CLI,
        "cwd=source_dir.absolute(), timeout=120",
        "cwd=compiled_grammar.parent.absolute(), timeout=120",
        DIGEST + "::test_remaining_public_adapters_two_paths[cli]",
    )
    add(
        "download_bare_cc",
        "chunker/grammar/download.py",
        "selected, grammar_path, output_file, scanner_priority=True",
        '"cc", grammar_path, output_file, scanner_priority=True',
        CONTRACT + "::test_controlled_failure_never_retries_legacy[download]",
    )
    for name, tool in (
        ("ugt_bare_git", "git"),
        ("ugt_bare_tree_sitter", "tree-sitter"),
        ("ugt_bare_npm", "npm"),
    ):
        add(
            name,
            "chunker/_internal/user_grammar_tools.py",
            f'selected_tools.require("{tool}")',
            f'"{tool}"',
            CONTRACT + "::test_user_tools_parent_resolution",
        )
    add(
        "sgm_bare_git_log",
        "chunker/_internal/grammar_management.py",
        'selected_tools.require("git")',
        '"git"',
        CONTRACT + "::test_smart_manager_git_log_parent_resolution",
    )
    add(
        "bare_git_checkout",
        CORE,
        '[selected_tools.require("git"), "checkout",',
        '["git", "checkout",',
        CONTRACT
        + "::test_installer_git_resolved_once_across_clone_checkout_and_commit",
    )
    add(
        "bare_git_rev_parse",
        CORE,
        '[selected_tools.require("git"), "rev-parse",',
        '["git", "rev-parse",',
        CONTRACT
        + "::test_installer_git_resolved_once_across_clone_checkout_and_commit",
    )
    add(
        "resolve_in_source_cwd",
        TOOLS,
        "return os.path.abspath(found) if found else None",
        "return found if found else None",
        CONTRACT + "::test_user_tools_parent_resolution",
    )
    add(
        "combined_legacy_api",
        BUILDER,
        "results = dict.fromkeys(languages, False)",
        '__import__("tree_sitter").Language.build_library("unused", [])\n        results = dict.fromkeys(languages, False)',
        CONTRACT + "::test_combined_never_uses_obsolete_binding_api",
    )
    add(
        "cli_skips_pin_admission",
        CLI,
        "if pin_provenance(self.trusted_artifacts, language) is None:",
        "if True:",
        "tests/test_validator_admission_contract.py::test_build_without_pin_is_not_admitted_and_with_pin_is_probed",
    )
    for prefix in ("individual", "download"):
        add(
            prefix + "_controlled_cxx_process",
            RECIPE,
            "    error = source_chain_error(root)\n    if error:\n        raise ValueError(error)",
            '    __import__("subprocess").run(["cc", "--version"], check=False)\n    error = source_chain_error(root)\n    if error:\n        raise ValueError(error)',
            CONTRACT + "::test_direct_controlled_helper_declines_cxx",
        )
    add(
        "individual_follow_symlink",
        RECIPE,
        "    root = root.absolute()\n    for path in reversed",
        "    return None\n    root = root.absolute()\n    for path in reversed",
        CONTRACT + "::test_individual_mapped_symlink_has_no_process",
    )
    for prefix, path, root in (
        ("manager", MANAGER, "self._grammars_dir"),
        ("combined", BUILDER, "self._source_dir"),
        ("individual", BUILDER, "lang_root"),
    ):
        indent = "                    " if prefix == "individual" else "        "
        old = "\n" + indent + 'logger.info("Controlled C build using %s", compiler)'
        new = (
            "\n"
            + indent
            + "cmd = [str(("
            + root
            + ' / arg).absolute()) if arg.endswith(".c") else arg for arg in cmd]'
            + old
        )
        add(
            prefix + "_absolute_sources",
            path,
            old,
            new,
            DIGEST + f"::test_remaining_public_adapters_two_paths[{prefix}]",
        )
    add(
        "cli_absolute_sources",
        CLI,
        "compile_result = self._run_command(",
        'cmd = [str((source_dir / arg).absolute()) if arg.endswith(".c") else arg for arg in cmd]\n                compile_result = self._run_command(',
        DIGEST + "::test_remaining_public_adapters_two_paths[cli]",
    )
    add(
        "download_absolute_sources",
        "chunker/grammar/download.py",
        "        try:\n            result = subprocess.run(\n                cmd,",
        '        cmd = [str((grammar_path / arg).absolute()) if arg.endswith(".c") else arg for arg in cmd]\n        try:\n            result = subprocess.run(\n                cmd,',
        DIGEST + "::test_remaining_public_adapters_two_paths[download]",
    )
    add(
        "platform_absolute_sources",
        PLATFORM,
        "cmd = _build_recipe.controlled_c_argv(compiler, sources, includes, lib_path)",
        'cmd = _build_recipe.controlled_c_argv(compiler, sources, includes, lib_path)\n        cmd = [str((self._grammars_dir / arg).absolute()) if arg.endswith(".c") else arg for arg in cmd]',
        DIGEST + "::test_remaining_public_adapters_two_paths[platform]",
    )
    add(
        "probe_failure_falls_back",
        CORE,
        "                        identity = None\n                record =",
        "                        continue\n                record =",
        DIGEST + "::test_build_methods_run_gcc_then_make_then_tree_sitter",
    )
    add(
        "fallback_after_timeout",
        CORE,
        '                    return False, None, f"Build aborted: {e}", None',
        "                    continue",
        DIGEST + "::test_build_methods_run_gcc_then_make_then_tree_sitter",
    )
    add(
        "missing_compiler_skips_ci",
        DIGEST,
        "        if _policy_required():\n            pytest.fail(",
        "        if False:\n            pytest.fail(",
        CONTRACT + "::test_missing_compiler_fails_required_policy",
    )
    add(
        "make_bare_executable",
        CORE,
        '[selected_tools.require("make")]',
        '["make"]',
        "tests/test_validator_admission_contract.py::test_fallback_bytes_still_require_raw_pin[make]",
    )
    add(
        "cli_fallback_bare_executable",
        CORE,
        'selected_tools.require("tree-sitter"),',
        '"tree-sitter",',
        "tests/test_validator_admission_contract.py::test_fallback_bytes_still_require_raw_pin[tree-sitter]",
    )
    add(
        "tree_sitter_first",
        CORE,
        "for name, build_method in build_methods:",
        "for name, build_method in reversed(build_methods):",
        DIGEST + "::test_build_methods_run_gcc_then_make_then_tree_sitter",
    )
    for name, method in (
        ("make_mismatch_accepted", "make"),
        ("cli_fallback_mismatch_accepted", "tree-sitter"),
    ):
        add(
            name,
            "chunker/_internal/native_admission.py",
            'if not hmac.compare_digest(content, pin.lower()):\n            return NativeProbeResult(False, "integrity_mismatch", None), None',
            'if not hmac.compare_digest(content, pin.lower()):\n            return NativeProbeResult(True, "ok", content), None',
            "tests/test_validator_admission_contract.py::test_fallback_bytes_still_require_raw_pin["
            + method
            + "]",
        )
    add(
        "make_claims_controlled",
        CORE,
        '"method": name,',
        '"method": "gcc",',
        "tests/test_validator_admission_contract.py::test_fallback_bytes_still_require_raw_pin[make]",
    )
    add(
        "cli_distutils_restored",
        CLI,
        "compile_result = self._run_command(\n                    cmd,",
        'compile_result = self._run_command(\n                    ["python", "compile.py"],',
        CONTRACT + "::test_cli_pregenerated_needs_no_node_or_generator[None]",
    )
    add(
        "controlled_failure_retries_legacy",
        BUILDER,
        "                    return success",
        '                    if not success:\n                        subprocess.run(["gcc", "-shared"], check=False)\n                    return success',
        CONTRACT + "::test_controlled_failure_never_retries_legacy[individual]",
    )
    for name, adapter in (
        ("download_wrong_install_name", "download"),
        ("platform_drop_install_name", "platform"),
    ):
        add(
            name,
            RECIPE,
            'return [f"-Wl,-install_name,@rpath/{basename}"]',
            "return []",
            CONTRACT + "::test_host_flags_use_actual_basename[" + adapter + "]",
        )
    add(
        "controlled_failure_retries_legacy",
        "chunker/grammar/download.py",
        "            if result.returncode != 0:\n                return CompilationResult(",
        '            if result.returncode != 0:\n                subprocess.run(["cc", "-shared"], check=False)\n                return CompilationResult(',
        CONTRACT + "::test_controlled_failure_never_retries_legacy[download]",
    )
elif sys.platform == "darwin":
    for name in (
        "drop_install_name",
        "download_wrong_install_name",
        "platform_drop_install_name",
    ):
        add(
            name,
            RECIPE,
            'return [f"-Wl,-install_name,@rpath/{basename}"]',
            "return []",
            DIGEST + "::test_remaining_public_adapters_two_paths",
        )
    add(
        "flags_from_label",
        RECIPE,
        "artifact_link_flags(output.name, sys.platform)",
        'artifact_link_flags(output.name, "Linux" if output.suffix == ".so" else sys.platform)',
        DIGEST + "::test_remaining_public_adapters_two_paths",
    )
elif sys.platform == "win32":
    add(
        "drop_no_insert_timestamp",
        RECIPE,
        '["-Wl,--no-insert-timestamp", "-Wl,--disable-auto-image-base"]',
        '["-Wl,--disable-auto-image-base"]',
        DIGEST + "::test_remaining_public_adapters_two_paths",
    )
    add(
        "drop_disable_auto_image_base",
        RECIPE,
        '["-Wl,--no-insert-timestamp", "-Wl,--disable-auto-image-base"]',
        '["-Wl,--no-insert-timestamp"]',
        DIGEST + "::test_remaining_public_adapters_two_paths",
    )


def main() -> int:
    if not os.environ.get("CI"):
        raise SystemExit("Mutation evidence must run on hosted CI (I6)")
    records = []
    for name, filename, old, new, test in MUTATIONS:
        path = ROOT / filename
        original = path.read_text(encoding="utf-8")
        if old not in original:
            raise RuntimeError(f"Mutation anchor missing: {name}: {old}")
        try:
            mutated = original.replace(old, new)
            compile(mutated, str(path), "exec")
            path.write_text(mutated, encoding="utf-8")
            # Do not reuse bytecode from a prior mutant with equal file size/mtime.
            for cache in path.parent.glob(f"__pycache__/{path.stem}.*.pyc"):
                cache.unlink()
            run = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "-rs", test],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
                timeout=300,
            )
            output = run.stdout + run.stderr
            killed = (
                run.returncode == 1
                and (
                    "AssertionError" in output
                    or "Failed:" in output
                    or "\nE   assert " in output
                )
                and "ERROR collecting" not in output
            )
            record = {
                "mutation": name,
                "test": test,
                "host": sys.platform,
                "returncode": run.returncode,
                "killed": killed,
                "run_url": f"https://github.com/{os.environ.get('GITHUB_REPOSITORY')}/actions/runs/{os.environ.get('GITHUB_RUN_ID')}",
                "output": output,
            }
            records.append(record)
            print(json.dumps(record), flush=True)
            if run.returncode < 0:
                break
        finally:
            path.write_text(original, encoding="utf-8")
            for cache in path.parent.glob(f"__pycache__/{path.stem}.*.pyc"):
                cache.unlink()
    return 0 if records and all(record["killed"] for record in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
