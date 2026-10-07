---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Detailed plan: Julia Unicode fixture encoding

## Task and research

Resolve treesitter-chunker#468 as one independently landable test setup repair.
Actual Windows CPython 3.13.15 with CP1252 defaults fails the existing real Julia
Unicode fixture at Path.write_text before parsing, at the Sigma identifier.
The source/test SHA and actual failing output are preserved in the originating
treesitter-chunker#465 reproduction packet. The existing test exercises Sigma,
Greek identifiers, mathematical operators and a rocket function through actual
chunk_file parsing. Nearby Julia writes contain ASCII only; no other Unicode
write in this module needs changing. There is no repository-wide fixture claim.

## Files and observable contracts

- Modify only tests/test_julia_language.py::TestJuliaEdgeCases::test_julia_with_unicode_identifiers:
  give the existing write explicit encoding="utf-8". Preserve literal source,
  assertions, function names and real parser API. No production/parser change.
- Own plans/detailed-julia-unicode-fixture-468.md and one manifest row:
  register typed detailed planning and executing lifecycle while preserving all
  canonical entries, current main and held evidence. No history rewrite.
- No README/AGENTS/CLAUDE/CONTRIBUTING/changelog change: this is test setup;
  explicit UTF-8 fixture guidance already exists, and there is no consumer delta.

## Dependencies and execution

1. Finish and archive treesitter-chunker#472 before basing a new private
   WORKTREE_ROOT checkout on accepted main. No concurrent original full runners
   or Git publication/mutations. Publish this plan-only draft before execution;
   planning runs no tests/builds.
2. Locked environment, narrow unchanged test on Linux, preserve baseline hash
   and historical actual Windows failure. Add only explicit UTF-8; run the
   real case, all Julia tests, Ruff/Black/type checks. Preserve source bytes.
3. Windows at exact published head: actual current real-parser test passes.
   Named test-contract mutation write_julia_unicode_fixture_with_platform_default
   removes only this encoding kwarg and must fail before parsing with the
   CP1252 UnicodeEncodeError. Restore byte-identical test and run the Unicode
   case plus the Julia module successfully. Record actual process exits and
   current source/test/support digests. This mutation establishes portable
   test setup, not a production bug kill. Linux's UTF-8 default does not kill
   this mutation; no Linux mutation success is claimed.
4. Fresh original six checks, locked refresh/full tests and spec_tests, exact
   Windows Julia focus and standing preflight, all required exact-head hosted
   checks. Four manual tools-enabled CODE seats: Opus 5.5 subscription TUI,
   Gemini 3.8 Flash, Astra, Sol, heartbeat only, maximum three complete rounds.
   Collect all substantive opinions before changes; failed/incomplete delivery
   is not a verdict. Supplemental Astra president checks frozen full evidence.
5. Standalone raw evidence archive precedes authorized exact-head qualified
   merge, comment/close treesitter-chunker#468, and owned worktree/review pruning.
   Lifecycle reconciliation remains treesitter-chunker#361; no frozen row edits.

## Verification and mutation

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_julia_language.py::TestJuliaEdgeCases::test_julia_with_unicode_identifiers -q
- uv run --locked --all-extras pytest tests/test_julia_language.py -q
- Repository Ruff, Black, mypy gate, CI smoke and Linux platform-core as original
  sealed six-check runner; uv run --locked --with toml --all-extras python scripts/run_full_suite.py
- Windows actual archived head, locked runtime, current default encoding recorded,
  named remove-encoding mutation with CP1252 UnicodeEncodeError and exact restore,
  Julia focus then scripts/run_windows_preflight.py. No encoding environment
  forcing, mocks of code under test or parser pin changes.

## Acceptance criteria

- [ ] Unchanged Julia Unicode source reaches actual chunk extraction on Linux
  and Windows with both existing Sigma and rocket function assertions passing.
- [ ] Actual Windows platform-default mutation reproduces only the known setup
  failure, exact restore passes the real case and Julia module, with immutable
  current test/source/support hash bindings and actual exits.
- [ ] Fresh sealed original six/refresh/full, current Windows/standing, all
  required exact-head hosted, four complete final opinions, supplemental Astra
  and standalone archive qualify this test repair before merge/prune.

## Limits and exclusions

No production change, global Unicode/grammar/chunk-selection/API parity,
new coverage-percentage gate, parser pins, goldens, type baseline, consumer locks,
protected ledger/checkpoints or broker edits. Other streaming, CR-only policy,
DOT, cache and native items remain separate. This is manual supplemental code
acceptance, not agent-harness#1271 governed amendment/supplier/native-fill/IF,
whole-phase or release acceptance. Unreleased stays reserved for 6.0.0; no tag.

