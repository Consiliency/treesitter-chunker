---
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_public_grammar_cli.py -q"
---

# Detailed plan: Honor the programmatic CLI cache option

## Task

Resolve treesitter-chunker#384 as a separate bounded API repair. The accepted
GrammarManager/GrammarInstaller repair in treesitter-chunker#381 does not cover
ComprehensiveGrammarCLI. Concurrent cache deletion remains treesitter-chunker#323.

## Research summary

ComprehensiveGrammarCLI.remove_grammar accepts clean_cache but adds its build
copy unconditionally. Existing public CLI removal tests cover default deletion,
confirmation and user/package ownership, using real parsed Python fixtures.

## Changes

- chunker/grammar_management/cli.py: include build_dir's compiled copy only when
  clean_cache is true. Always remove installed user source/libraries; preserve
  packaged libraries. Keep defaults and existing argument positions.
- tests/test_public_grammar_cli.py: exercise both boolean values through the
  actual programmatic method with explicit roots, actual native file bytes and
  a real nonempty Python parse. Assert installed/source removal, build-copy
  preservation/deletion and package preservation. Keep existing Click tests.
- docs/grammar_management.md and CHANGELOG.md: define the compiled build copy as
  cache for this API and explain that the Click command retains default cleanup.
- This plan and its typed plans/manifest.json entry are owned control artifacts.

## Documentation impact

Update the existing programmatic-access guide; no new CLI flag or public symbol.

## Dependencies and order

Current main is the base. Register the plan before editing source, add the test,
confirm the false-option regression, repair it and verify. File unrelated defects
separately; no parser-pin, consumer-lock, transaction or native-admission change.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_public_grammar_cli.py -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --all-extras pytest -q

Kill cli_always_clean_build_copy by removing the boolean condition. Require the
preservation assertion to fail and the restored public CLI module to pass. Run
standing Windows preflight and changed-source flag tests before publication;
require exact-head hosted Linux/macOS/Windows and manual tool-enabled code review.

## Acceptance criteria

- [ ] False preserves the build copy, true deletes it, both remove installed user
  components and leave packaged artifacts unchanged.
- [ ] Real fixture parse and default Click removal remain valid; the named
  mutation fails at the preservation assertion and restored tests pass.
- [ ] Original runner checks, changed platforms and code review accept the slice;
  docs describe this API without claiming concurrent deletion safety.
