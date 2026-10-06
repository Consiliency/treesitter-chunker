---
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_grammar_compatibility_contract.py -q"
---

# Detailed plan: Confine compatibility helper cache activity

## Task

Resolve the remaining treesitter-chunker#136 constructor leak and its coupled
GrammarTester defect treesitter-chunker#395. The registry
propagation portion is already fixed by treesitter-chunker#381. This is a bounded
private-storage delivery under EC-CACHE-2, not complete CACHE acceptance.

## Research summary

GrammarManager forwards its explicit cache directory to its own installer and
validator and to GrammarRegistry, which forwards it to its installer. However,
CompatibilityChecker constructs GrammarValidator() by default, creating an
operator-home cache despite receiving an explicitly isolated manager. It already
accepts an optional validator; that caller-supplied object must retain priority.
GrammarTester has the same default constructor gap and optional injection.

## Changes

- chunker/grammar_management/compatibility.py: default CompatibilityChecker and
  GrammarTester validators to the supplied GrammarManager's existing _cache_dir. Keep the
  current optional validator argument and its precedence; no new public API.
- tests/test_grammar_compatibility_contract.py: use actual manager/checker/tester,
  optional actual supplied validator and private HOME/USERPROFILE. Parse the real
  checked-in Python fixture through the helper. Validate an actual directory as
  a rejected grammar to exercise real JSON cache writes without native loading.
  Assert every manager/registry/helper cache root, persisted rejection and absent
  operator-home cache; an explicitly supplied validator uses its own caller root.
  Do not mock production constructors, validators, parsers or cache operations.
- docs/grammar_management.md and CHANGELOG.md: explain default cache propagation
  and explicit validator precedence. This plan and typed manifest row are owned.

## Dependencies and order

Plan on current main; do not edit the shared compatibility.py until the accepted
connection-lifetime repair treesitter-chunker#394 is merged. Integrate its exact
main history before implementation. Register this plan before product edits,
reproduce the leaked home directory, fix and verify. Registry tests establish
the already landed portion; no unrelated constructor changes or schema work.
JSON writer coordination remains treesitter-chunker#370 and parallel extraction
identity remains treesitter-chunker#358. Admitted ledgers and checkpoints, parser
pins and consumer locks are preserved.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_grammar_compatibility_contract.py -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --all-extras pytest -q

Kill helper_ambient_cache_root by restoring both unscoped default validators. The
real temporary-home assertion must fail and all focused tests must restore.
Require changed-source Windows cases and exact-head hosted platforms (the existing
common selection already runs this module), plus manual tool-enabled code review.
No coverage or timing gate, native admission or concurrent-writer safety claim.

## Acceptance criteria

- [ ] An explicit manager cache root confines default registry/installer/validator
  and checker/tester cache creation and actual persisted rejection data, with no home cache.
- [ ] An actual caller-supplied validator is preserved and parses the nonempty
  fixture, while its cache writes remain in its explicitly selected root.
- [ ] The named mutation fails and restores; original runner, changed platforms
  and code review accept the bounded repair with matching documentation.
