---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Detailed plan: Exclude unnamed Python keyword chunks

## Task

Resolve treesitter-chunker#446 in normal and streaming Python chunk selection.
Complete named lambda expressions remain chunks; unnamed keyword leaves never
become Python chunks. Preserve named function/class selection, routes, parents,
content, byte spans and retained chunk IDs. The output removes erroneous chunks
and belongs with accumulated Unreleased changes reserved for 6.0.0.
Regular extraction retains its ignored-subtree rules. Streaming traversal of
ignored strings is separately tracked in treesitter-chunker#466; this slice
does not repair that policy or certify parity outside its fixture contracts.

## Research summary

`core._walk` and `StreamingChunker._walk_streaming` both exclude unnamed nodes
only for Ruby. Python's configured `lambda` type matches both named expressions
and unnamed keyword leaves. The accepted issue reproduction parses the real
`tests/fixtures/graph_same_span.py` without errors and finds two keyword-only
chunks. Existing standalone/nested/complex lambda tests pin inflated totals,
so they need explicit expression contracts alongside the fix. Both walkers
already share type predicates; extend their existing unnamed exclusion only to
Python, preserving Ruby and all other languages. No new selector abstraction.

## Changes

### `chunker/core.py`, `chunker/streaming.py` (modify)

- Extend the existing early unnamed-node exclusions from Ruby to Ruby/Python.
  Keep all named selection, ignored-type semantics, recursion, metadata,
  identities and language-specific transformations unchanged.

### `tests/test_python_language.py` (modify)

- Strengthen the three existing standalone/nested/complex lambda cases with
  exact complete-expression content and byte spans instead of totals that
  include keyword leaves. Keep their existing function/context checks.
- Add parameterized actual regular/streaming runs, with/without retrieval
  metadata, on the real same-span fixture. Parse its actual bytes and collect
  named lambda AST spans plus distinct unnamed keyword spans independently.
  Assert every named lambda appears once, no unnamed span appears, contents
  match exact source slices, and named function/class controls remain.
- Compare both actual APIs on complete node-type/span/content/node-ID/parent-ID/
  route/qualified-route tuples for the same fixture path; assert lambda parent
  is the actual enclosing function and same-line siblings remain distinct.
  Use the same canonical absolute fixture path for both APIs. Existing Python
  class cases supply named-class controls; the new same-span fixture supplies
  function and lambda controls. No parser, walker, filesystem or metadata mocks.

### `docs/chunk-identity.md`, `CHANGELOG.md` (modify)

- Document Python named-expression selection and removal of keyword-only
  lambda records in both APIs. Existing real occurrence identity algorithm is
  unchanged. Preserve streaming language exceptions and the 6.0.0 migration.
  Cache reuse through parallel helpers remains treesitter-chunker#358; advise
  `use_cache=False` for the changed extraction contract until its cache identity
  repair is accepted. This slice does not certify cached parallel parity.

### Own plan and `plans/manifest.json` (modify)

- Register only this detailed-plan row; preserve all canonical rows during
  prerequisite integration. Record own executing lifecycle before source edits.
  No admitted ledger/checkpoint, parser pin, golden or consumer-lock changes.

## Dependencies & order

1. After the active original runner completes, create a private worktree and
   publish a plan-only draft. Planning performs no tests/builds. Implementation
   waits for accepted treesitter-chunker#462 and canonical current-main integration.
2. Add declared contracts and strengthen explicitly incorrect old assertions.
   Reproduce new contracts against unchanged accepted production. Audit actual
   streaming results before claiming parity. File additional independent defects
   separately, without silently expanding the selector repair.
3. Extend the two existing guards. Run named mutations
   `select_unnamed_python_core` and `select_unnamed_python_streaming`, each removing
   Python only from its corresponding guard. Require declared API cases to fail,
   other API/named-expression controls to retain behavior, and exact restoration
   to pass with source/test/fixture/support hashes and actual logs/exits.
4. Verify narrowly, then original six/locked refresh/full tests/spec_tests under
   short private TMPDIR `/mnt/workspace/worktrees/viperjuice/t446`. Confirm retained
   graph/parent/span controls; never edit parser pins or hand-edit Boundary goldens.
   If a generated interface change beyond removal of declared keyword chunks
   appears, stop and separately scope it before any intentional regeneration.
5. Verify actual exact-head Windows focus and unchanged standing preflight,
   required hosted jobs and four manually launched tools-enabled CODE seats:
   Opus 5.5 TUI, Gemini 3.8 Flash, Astra, Sol. Compact pointers, max three complete
   substantive rounds, heartbeat only/no model or silence deadlines. Collect all
   opinions before reconciliation; require final manual Astra chair, archive,
   exact-head merge, qualified issue comments/closure and safe owned pruning.

## Verification

- `uv sync --locked --all-extras`
- Narrow: `uv run --locked --all-extras pytest tests/test_python_language.py -q`
- Focus: `uv run --locked --all-extras pytest tests/test_python_language.py tests/test_streaming.py tests/test_ruby_language.py tests/test_spans_roundtrip.py tests/test_hierarchy.py tests/test_core_span_consistency.py tests/test_graphml_exporter.py tests/test_graphml_yed_export_contract.py -q`
- `uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site`
- `uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/`
- `uv run --locked --all-extras python scripts/mypy_gate.py`
- `uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py`
- `uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux`
- `uv run --locked --with toml --all-extras python scripts/run_full_suite.py`

Windows runs the same focused contracts and unchanged standing preflight.
The private `chunker-446-` packet binds actual baseline/mutations/restorations,
Windows stage/launcher exits, original sealed runner JSON/log, four raw reviews
and final manual chair. This supplemental evidence is not agent-harness#1271's
governed operational amendment, supplier/native-fill/IF or release acceptance.
No coverage-percentage, performance or duration acceptance gate is introduced.

## Acceptance criteria

- [ ] Real regular and streaming fixture results contain complete named lambda
  expressions exactly once and exclude unnamed keyword spans with/without
  retrieval metadata; named declarations/content/spans remain, proven by narrow
  and focused commands.
- [ ] Actual shared-path API tuples preserve IDs, parent relationships and
  routes for named chunks and keep same-line siblings distinct; Ruby, span,
  graph and hierarchy controls pass the focused command.
- [ ] Both named mutations fail the corresponding API contract and exact
  restoration passes with bound evidence; docs describe the intended output
  removal without changing identity algorithms or protected pins/goldens/rows.
- [ ] Original six/refresh/full valid seal, current Windows/standing, exact
  hosted, all four substantive code agreements and final manual Astra ruling
  qualify only this selector repair; independent defects are separately filed.

## Execution notes

Accepted treesitter-chunker#462 was integrated before execution, preserving all
58 canonical manifest rows plus this own row. The unchanged production baseline
fails seven strengthened/new Python contracts with 36 controls passing. On the
formatted candidate, `select_unnamed_python_core` fails seven cases (36 pass),
and `select_unnamed_python_streaming` fails four (39 pass). These include the
affected API's two metadata-mode selection cases and both API-parity cases;
the other API's selection cases pass. Each exact restoration passes all 43.
The core mutant also fails the three strengthened regular lambda cases.

Actual before/after snapshots for both APIs and both metadata modes retain exact
named-chunk contents, spans, IDs, parents and routes for the canonical same-span
fixture, removing only the two keyword records per result. These observations
do not establish global metadata, cache or cross-language parity. The formatter
only adjusted changed source/test layout; final gates must bind formatted bytes.
A first private mutation helper referenced a nonexistent identity module and
failed before any mutation; actual identity functions live in `chunker/types.py`.
The corrected helper and raw setup failure are preserved, with no passing gate
claimed for the failed attempt. No type-baseline update is performed.

Original six/locked refresh/full suite, fresh exact-head Windows focus/standing,
hosted checks, four substantive manual CODE reviews and final supplemental Astra
chair remain required. Their completion is recorded in the immutable private
packet and acceptance comment, rather than changing reviewed candidate bytes.

### R1 hold and R2 reconciliation

All four R1 opinions and the original runner completed before reconciliation.
Opus and Astra returned PARTIALLY AGREE because the three strengthened lambda
fixtures used platform-translated writes while asserting LF byte offsets;
Gemini and Sol returned AGREE. The original six checks, locked refresh and full
suite passed (4431 passed, four skipped), but the actual Windows focused run
failed six cases and did not reach its standing preflight. Its driver returned
one. The R1 head, raw opinions, passing original seal and failed Windows logs
are preserved as excluded history, not acceptance for the new candidate.

Accepted treesitter-chunker#467 / treesitter-chunker#465 and
treesitter-chunker#469 / treesitter-chunker#464 / treesitter-chunker#470 resolve
the inherited Windows Unicode/permission and raw newline/CLI oracle failures.
Their accepted main was integrated by normal merge, retaining all 60 canonical
manifest rows plus this own row, with no force, rebase, parser-pin or golden
change. The raw decoder and its migration remain prerequisite behavior rather
than a selector workaround. The three strengthened lambda fixtures now write
explicit UTF-8 and LF; their source text and exact expression/span assertions
are unchanged. Identity guidance explicitly separates the ignored-string
streaming gap in treesitter-chunker#466.

R2 requires fresh current-byte baseline and both named selector mutations with
opposite-API controls, exact restorations and retained named tuple snapshots.
The expanded focused group includes accepted raw-span contracts. Fresh original
six/refresh/full, actual Windows mutation/restore/focus/standing, exact hosted
checks, all four manual tools-enabled CODE R2 reviews and the supplemental Astra
chair must complete before acceptance. R2 is the second of at most three
complete substantive code rounds; no R1 result substitutes for a current gate.

An initial R2 focused run overlapped local mutation preparation and is excluded
as independent evidence; a fresh focused run after exact restoration passes
563 tests. An initial private snapshot helper passed an unsupported constructor
argument to StreamingChunker and failed; its finally block restored both source
files exactly. The corrected public streaming API helper captures all four
API/metadata projections successfully, retaining four named tuples and removing
two keyword records each. Both setup histories are preserved separately.
