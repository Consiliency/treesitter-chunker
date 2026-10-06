# Bounded repair: treesitter-chunker#365

## Contract

Filesystem timestamps are not grammar version or release evidence. Preserve
existing embedded-version extraction, return an explicit `unknown` when it finds
no version, and leave `GrammarVersion.release_date` as None without authentic
release metadata. Identical compiled bytes with different mtimes give identical
artifact version/date fields. Reports and exports preserve the unknown value.

This repair does not secure native admission, cache identity or arbitrary string
attribution. Those contracts remain independently reviewed in the cleanup
roadmap. It does not claim that an empty library is supported safely.

## Owned files and steps

- `chunker/languages/compatibility/grammar_analyzer.py`: remove mtime version and
  release-date inference; retain existing metadata extraction.
- `tests/test_compiled_grammar_analysis_contract.py`: compile repository BAML,
  remove compiler comment metadata in the temporary artifact, prove actual
  declarations parse, and compare identical copies with different mtimes using
  fresh analyzers. Check unknown versions, None dates, reports and JSON exports.
- `docs/grammar_management.md`, `CHANGELOG.md`: document the changed unknown
  metadata contract without claiming the pending native safety repairs.
- This plan is a control artifact.

## Verification and review

Run the new regression against old code and record its failure; then run the
compiled-contract and grammar-management tests. Kill `infer_version_from_mtime`
by restoring the timestamp fallback, require regression failure, restore the
repair and rerun. Also kill `infer_release_from_mtime` by restoring the old
release-date argument, then restore and rerun. Use temporary compiled artifacts,
no mocks of the analyzer.
The native reproduction uses the existing Linux ELF fixture conventions;
record that scope, and require hosted platform checks before merge.

Run Ruff, Black, mypy gate and CI smoke using the locked environment, then
standing Windows preflight before publication because the defect concerns file
metadata. Run strict docs to a temporary destination. Publish a draft through
the supported adapter, manually panel the exact code head with tool-enabled
Opus 5.5 TUI, Gemini 3.8 Flash, Astra and Sol, and reconcile blocking findings
within three substantive rounds. On a surviving blocker, keep the PR draft;
never waive it. Merge only after acceptance, comment before closing
treesitter-chunker#365, then prune the clean merged worktree.

## Local verification

The new regression failed against unchanged code at the timestamp-version
assertion. The repair passed both focused files: 32 tests. Restoring each named
mutation failed at its intended version/date assertion; restored code passed
32 tests. Ruff and Black passed, mypy reported no new errors, and CI smoke
passed 770 tests. Standing Windows main preflight passed 148 tests with one
skip; it supplements, rather than replaces, changed-head hosted CI. Raw command
logs are private operational outputs under `/tmp/chunker-365-*.log`; no native
artifact, fixture golden or parser pin was committed. Exact-head review and
hosted platform acceptance remain pending.
