---
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_nullable_compatibility_history.py tests/test_grammar_compatibility_contract.py tests/test_grammar_compatibility_cleanup_contract.py -q"
---

# Detailed plan: Canonical nullable compatibility history without data loss

## Task

Resolve treesitter-chunker#135 as one independently landable persistence repair
within EC-COMPAT-1. An unspecified language version has one canonical record,
and a fallback read reports its actual stored version. This does not complete
the COMPAT phase or repair the other compatibility database implementation.

## Research summary

The grammar-management CompatibilityDatabase in
chunker/grammar_management/compatibility.py uses a nullable three-column UNIQUE
constraint and INSERT OR REPLACE. SQLite allows repeated NULL versions, and
get_compatibility_result orders exact and fallback matches only by timestamp,
then replaces their stored version with the requested one. Existing real-parser
tests derive persisted results from fixture parses and reopen actual SQLite.
The separately named chunker/languages/compatibility/database.py is outside
this defect. Accepted treesitter-chunker#394 connection closure must remain.

## Changes

### chunker/grammar_management/compatibility.py (modify)

- CompatibilityDatabase._init_database: after existing schema initialization,
  migrate unspecified-version duplicates in an explicit BEGIN IMMEDIATE
  transaction. Within each (language, grammar_version) group, retain the row
  with greatest timestamp, breaking timestamp ties with greatest original id.
  Preserve every displaced row, including original id and every stored column,
  in compatibility_results_null_archive before deleting it from canonical
  storage. Create the archive with the existing table's complete column shape
  and an original-id unique index; it is migration history, not lookup data.
  Create a partial unique index on (language, grammar_version) WHERE
  language_version IS NULL after reconciliation. Commit all migration writes
  together, roll back and propagate failure on any migration error. Reopening
  an already migrated database is idempotent. No version sentinel, irreversible
  drop, rewriting payload JSON or deletion of displaced history.
- store_compatibility_result: retain existing replacement behavior for concrete
  versions and let the partial unique index give NULL writes the same latest
  write replacement semantics. Neither path rewrites another version's row.
- get_compatibility_result: select the stored language_version, prefer a matching
  concrete version over any NULL fallback regardless of timestamps, and return
  the stored version. An unspecified request only matches NULL; a concrete
  request with no exact row may still fall back to NULL, reported as None.
  Retain deterministic timestamp/id ordering within each priority. Missing
  language/grammar returns None. Preserve current level/JSON decoding and
  connection lifetimes. Other public history/stats/retention APIs operate on
  canonical rows; the legacy archive is intentionally excluded and retained.

### tests/test_nullable_compatibility_history.py (create)

- Derive compatible/incompatible result payloads from parsing the checked-in
  Python service fixture and actual malformed Python with the installed parser.
  Build legacy SQLite tables through SQL, not production/parser/DB mocks.
- Exercise repeated NULL writes, concrete-version replacement and unrelated
  keys with a fresh actual database and a cold reopen. Assert exact counts and
  actual payload/version identity, including newer fallback versus older exact.
- Seed duplicate NULL legacy rows with distinct complete payloads, out-of-order
  timestamps and a tied timestamp. Reopen through the actual constructor; assert
  the deterministic retained original id and every displaced column/value in
  the archive. Assert concrete rows, test results and grammar metadata survive.
  Reopen again, write a replacement and require unchanged migration archive.
- Create a real SQLite BEFORE DELETE trigger that raises ABORT to interrupt
  migration after archive insertion. Require the constructor to raise, all
  original rows/payloads to survive, and no partial archive/index migration.
  Remove the test trigger and reopen successfully. Direct SQL must reject a
  second NULL canonical row after migration, proving the database constraint.
- Kill four named mutations: omit_null_unique_index,
  prefer_recent_fallback_over_exact, relabel_fallback_as_requested_version and
  discard_displaced_legacy_records. Run them serially, restore exact bytes and
  pass the entire focused batch after each; clear only this module's generated
  bytecode where needed.

### docs/grammar_management.md and CHANGELOG.md (modify)

- Document canonical unspecified-version replacement, exact-before-fallback
  lookup, actual returned version and transactional automatic migration with
  the complete displaced legacy rows retained in the named archive table.
  Describe that canonical history/stats/cleanup exclude the archive, and that
  archive removal/export is an explicit operator concern outside this repair.
  Consumers must not infer that a fallback proved the requested language version.
- This detailed plan and plans/manifest.json are the owned control paths.

## Documentation impact

This is an observable persistence and lookup correction. Existing callers can
receive None as language_version for a fallback, rather than a falsely asserted
requested version. A database backup remains advisable before moving between
old/new software versions; old writers benefit from the database unique index.
No new CLI, data deletion command or independent schema-version system.

## Dependencies and order

Register this plan before product edits. Integrate accepted treesitter-chunker#404
for treesitter-chunker#345 before implementation: both own compatibility.py.
Reproduce real SQLite failures first, then implement and verify the migration
and lookup contracts. Serialize mutations and original full runners. Collect
each complete manual review round before fixing; maximum three substantive
rounds. Run the original five checks, dependency refresh/full suite, actual
changed-source Windows plus standing preflight and exact hosted platforms.
External panel/platform records are supplementary manual evidence, not formal
IF proof; no runner amendment is invented. Publish through the supported adapter.
Do not edit native admission, parser pins, consumer locks, ledgers or checkpoints.
Any independent defect discovered is filed separately before scope expansion.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_nullable_compatibility_history.py tests/test_grammar_compatibility_contract.py tests/test_grammar_compatibility_cleanup_contract.py -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --all-extras pytest -q

## Acceptance criteria

- [ ] EC-COMPAT-1 persistence subset: repeated NULL/concrete writes and reopened
  reads obey canonical replacement and exact-before-fallback selection; returned
  version/payload identity is truthful. Proven by the focused batch and the
  first three named mutations, without whole-phase acceptance.
- [ ] Legacy duplicate reconciliation is deterministic, idempotent and preserves
  every displaced complete row; a real interrupted migration rolls back fully
  and is safely retryable. Proven by legacy/trigger tests and the archive mutation.
- [ ] Actual fixtures, all original gates, Windows, hosted platforms and bounded
  manual reviews accept the exact repair with accurate migration documentation.
