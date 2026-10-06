---
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_grammar_compatibility_cleanup_contract.py tests/test_grammar_compatibility_contract.py -q"
---

# Detailed plan: Close compatibility database connections per operation

## Task

Resolve treesitter-chunker#388 independently of the accepted auxiliary containment
in treesitter-chunker#385. Keep schema, records, signatures and existing error
semantics. No persistence framework or native/cache IF claim.

## Research summary

The grammar-management CompatibilityDatabase has eight sqlite3.connect transaction
contexts. A connection context commits or rolls back but does not close; cyclic
SQLite objects can retain handles until GC and prevent Windows deletion. Cleanup
uses its connection after the transaction context for VACUUM, which must remain
outside the delete transaction but inside the explicit connection lifetime.

## Changes

- chunker/grammar_management/compatibility.py: wrap each operation's real connection
  with contextlib.closing while retaining its transaction context. For cleanup,
  use an outer closing context and inner delete transaction, then VACUUM before
  closing. Do not change catches, schema, serialization or return contracts.
- tests/test_grammar_compatibility_cleanup_contract.py: use real parsed fixture
  data and actual SQLite to exercise initialization, stores, read/history/trends,
  cleanup and stats, including constraint, query and mid-delete failures. Disable
  cyclic GC only during the observed operation; assert no open database handle
  and immediate unlink afterward. Check persisted values, committed cleanup and
  rolled-back first deletion on second-delete failure. No mocked connections.
- docs/grammar_management.md and CHANGELOG.md: state per-operation connection
  closure and transaction/VACUUM ordering. This plan and its typed manifest entry
  are owned controls.
- scripts/run_platform_core.py: select the real cleanup/lifetime module on all
  three hosted platforms so the new handle and rollback contracts run in CI.

## Dependencies and order

Start from current main. Register the plan before source edits, reproduce a real
handle leak with GC disabled, repair contexts and verify. Preserve all unrelated
main manifest rows when integrating accepted neighboring slices. File unrelated
defects separately; parser pins and consumer locks are untouched.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_grammar_compatibility_cleanup_contract.py tests/test_grammar_compatibility_contract.py -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --all-extras pytest -q

Kill omit_database_connection_close by restoring transaction-only contexts in
the initializer and ordinary operations; the real handle assertion must fail.
Restore and pass the focused modules. Require changed-source Windows lifetime
cases, exact-head hosted Linux/macOS/Windows, and manual tool-enabled code review.
No coverage-percentage or timing gate.

## Acceptance criteria

- [ ] All eight operations close their real SQLite handles on success and tested
  failure paths without needing GC; immediate Windows unlink succeeds.
- [ ] Records/schema survive; successful cleanup commits before VACUUM, and a
  failed second deletion rolls back the first. Error contracts stay unchanged.
- [ ] The named mutation fails and restores; original runner, changed platforms
  and code review accept the bounded repair.
