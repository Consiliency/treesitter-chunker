---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Detailed plan: Portable Windows Unicode and permission test setup

## Task

Resolve treesitter-chunker#465 as a test-only platform contract repair, separate
from treesitter-chunker#446 selection and treesitter-chunker#464 raw-file decoding.
Preserve real Unicode extraction coverage and actual POSIX read-denial checks.

## Research summary

Actual Windows treesitter-chunker#463 validation fails the unchanged Unicode
fixture before extraction because its default write encoding is CP1252.
The unchanged streaming permission test treats chmod(0) as POSIX read denial,
which Windows does not implement. Both function bodies are byte-identical to
accepted main, proven in `/tmp/chunker-446-inherited-windows-test-bindings.json`.
The complete six-failure Windows record is preserved; only these two failures
belong to this slice. Static decoding of the outer test string confirms the
Unicode fixture contains a valid closing quote; no fixture syntax repair is needed.

## Changes

### `tests/test_python_language.py` (modify)

- Give only `test_unicode_and_encoding` fixture creation explicit UTF-8.
  Preserve original source and Unicode/chunk assertions; do not silently repair
  parser-selection, newline offsets or unrelated fixture syntax.

### `tests/test_streaming.py` (modify)

- Add the conventional platform import and a Windows-only skip to the existing
  chmod-denial test. Keep actual chmod(0), PermissionError observation and finally
  restoration/unlink on POSIX. State that Windows ACL denial is not exercised.
  No production permission handling, ACL changes or bypasses.

### `CONTRIBUTING.md` (modify)

- Document explicit UTF-8 fixture I/O and the POSIX-only chmod-denial contract;
  Windows exercises actual parsing and deliberately skips that permission test.
  No changelog delta: there is no consumer-facing extraction/API change.

### Own plan and `plans/manifest.json` (modify)

- Register this own detailed-plan entry and executing lifecycle, preserving all
  current canonical rows. Record evidence and limits without rewriting history.

## Dependencies & order

1. Wait for the active original runner before any Git publication/mutations.
   Publish plan-only draft from current accepted main under private WORKTREE_ROOT.
   Planning runs no tests/builds. Keep treesitter-chunker#463 frozen and unmerged.
2. Apply only the two declared test platform corrections. Preserve baseline
   bodies and actual failed Windows outputs before edits.
3. Run the Unicode and permission cases narrowly on Linux and actual Windows.
   Windows must exercise real Unicode extraction and skip only the explicitly
   unsupported chmod contract; Linux must exercise both actual cases.
4. On actual Windows, named mutation `write_unicode_fixture_with_platform_default`
   removes the encoding kwarg and must reproduce UnicodeEncodeError; exact restore
   must pass. Named mutation `assert_windows_chmod_read_denial` removes only the
   declared Windows skip and must reproduce the false PermissionError expectation;
   exact restore must recover the deliberate skip. Record raw outputs/actual
   exits and source/test/support hashes. These are test-contract mutations, not
   production bug kills. No failed setup is reported as parser acceptance.
5. Original six/locked refresh/full suite, exact-head Windows narrow/standing,
   hosted jobs and four manual tools-enabled CODE seats (Opus5.5 TUI,
   Gemini3.8Flash, Astra, Sol; max3 rounds, heartbeat only) precede supplemental
   Astra chair, standalone archive, authorized exact-head merge and owned pruning.

## Verification

- `uv sync --locked --all-extras`
- `uv run --locked --all-extras pytest tests/test_python_language.py::test_unicode_and_encoding tests/test_streaming.py::TestStreamingErrorRecovery::test_permission_error_handling -q`
- Repository Ruff, Black, mypy gate, CI smoke and Linux platform-core commands
  from CONTRIBUTING.md, run by the original sealed six-check runner.
- `uv run --locked --with toml --all-extras python scripts/run_full_suite.py`
- Actual Windows executes the exact narrow command, the two named mutations and
  unchanged `scripts/run_windows_preflight.py`, with actual stage/launcher exits.

The private `chunker-465-` packet binds current test/source hashes, Windows
mutations/restorations, actual scope/skips, sealed original runner, hosted checks,
four raw reviews and final chair. Supplemental, not agent-harness#1271 governed
amendment or supplier/native-fill/IF/release acceptance. Unreleased6.0.0 remains.

## Acceptance criteria

- [ ] The unchanged Unicode fixture reaches real chunk extraction on Linux and
  Windows with its literal Unicode assertions, proven by the narrow command.
- [ ] POSIX actually observes denied reading and cleans up; Windows has the
  explicit documented skip, proven by the same narrow command/platform record.
- [ ] Both actual Windows named mutations reproduce their specific fixture or
  unsupported-permission failures, with exact restorations passing/skipping and
  immutable current test/source/support hashes.
- [ ] Fresh sealed original checks/refresh/full, current Windows/standing, exact
  hosted, four completed substantive opinions and final chair qualify only this
  test repair. Production selection/decoding and protected pins/state unchanged.

## Execution notes

All four manual CODE R1 opinions completed with actual exit zero before changes.
Opus PARTIALLY AGREED because a repository-wide UTF-8 assertion exceeded this
two-test repair; Gemini, Astra and Sol agreed. CONTRIBUTING now specifically
describes the Python fixture. The extra EOF blank reported by Astra/Sol is removed
in the same documentation reconciliation. No test, production or manifest bytes
change from R1. Julia fixture encoding remains outside this slice; an additional
concrete reproduction is tracked separately if confirmed.

R1 original six/locked refresh/full passed 4425 with four skips, and actual
Windows baseline/mutations/restores/current focus and standing passed their stated
contracts. These and raw partial/agreement opinions remain preserved and excluded
from final R2 acceptance. A premature root freeze attempt rejected the partial
opinion after copying generated coverage and writing an early spec snapshot; no
frozen input map, chair or accepted proof was created. Original evidence/source
unchanged. R2 requires fresh original/current Windows/hosted/four-seat gates and
supplemental final chair at its own head; no opinion or failed gate is rewritten.
