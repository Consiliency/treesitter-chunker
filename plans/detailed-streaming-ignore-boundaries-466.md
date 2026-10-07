---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Detailed plan: Honor configured streaming ignore boundaries

## Task and research

Resolve treesitter-chunker#466 by retaining regular extraction's configured
ignored-subtree policy in streaming traversal. Python ignores `string` and
`comment`; JavaScript and TypeScript ignore `template_string` and `comment`.
Regular `_walk` stops before traversing ignored nodes. Streaming resolves the
same predicate pair but discards the ignore predicate, permitting named
expressions inside ignored interpolations. The actual issue reproduction parses
a Python f-string without errors and returns an extra named streaming lambda.

Accepted treesitter-chunker#463 / treesitter-chunker#446 supplies the unnamed
Python guard. Preserve it, the raw-newline and fixture prerequisites, identity
algorithms and per-language span transformation exceptions. Honoring the
existing ignore predicate is one behavior cluster; no new policy configuration.

## Owned changes

- `chunker/streaming.py`: append an optional ignore predicate to the existing
  private walker signature, preserve existing positional callers, resolve any
  missing predicate without replacing an explicitly supplied chunk predicate,
  return at ignored nodes, and thread both predicates through recursion.
  The public file entrypoint resolves the pair once. VFS's existing direct
  three-argument walker call continues to use defaults. No VFS source change.
- `tests/test_streaming.py`: add real-parser Python/JavaScript/TypeScript cases
  with both retrieval modes and both public file APIs. Independently inspect
  named expression AST spans and actual ignored ancestors; verify omission of
  hidden expressions, retention of visible expressions exactly once, exact
  source slices, enclosing chunks, real parents/routes and occurrence IDs.
  Compare declared same-path tuples across APIs without global metadata claims.
  Actual in-memory VFS streaming uses the same fixture bytes and identity path,
  proving the direct default-resolution path without filesystem/parser mocks.
- Three checked-in fixtures:
  `tests/fixtures/streaming_ignore_boundaries.py`, `.js`, `.ts`. Each contains a
  visible expression, an actual expression nested in an ignored interpolated
  string, ordinary text and comment controls. AST parsing must be error-free;
  ordinary text resembling code must not be treated as parsed expressions.
  Fixture writes, if copied, use bytes or explicit UTF-8/LF.
- `docs/chunk-identity.md`, `CHANGELOG.md`: document streaming output removal
  for configured ignored subtrees, retained visible IDs and ancestor source
  text, fixture-scoped parity, and the accumulated 6.0.0 migration. Existing
  cache advice for treesitter-chunker#358 remains necessary.
- Own plan and `plans/manifest.json`: preserve all 61 accepted canonical rows,
  append only this row and record its own executing lifecycle before edits.

## Order and verification

1. Create/register a plan-only draft from accepted main. No tests or builds
   during planning. Roadmap authorization permits the separate implementation
   step after the plan is published; all prior original runners are complete.
2. Add fixtures and observable tests first. Run the narrow new contracts against
   unchanged accepted production; require real hidden-expression failures and
   passing regular/visible controls. File independently discovered defects as
   separate qualified issues instead of silently fixing them here.
3. Implement only the ignore-boundary repair. Named mutations:
   `traverse_ignored_streaming_subtrees` removes the early ignore return;
   `ignore_only_chunkable_streaming_nodes` wrongly applies ignoring only to
   chunkable nodes. Both must expose hidden expressions while positive visible
   and regular controls remain. Bind actual source/test/fixture/support bytes,
   failure nodes, exits and exact passing restorations. Direct VFS default
   resolution is required by a separate observable case, not a mocked call.
4. Format before final mutation/snapshot binding. Run narrow contracts, then
   focus: `tests/test_streaming.py tests/test_python_language.py
   tests/test_javascript_language.py tests/test_typescript_language.py
   tests/test_ruby_language.py tests/test_spans_roundtrip.py tests/test_vfs.py
   tests/test_hierarchy.py tests/test_core_span_consistency.py`.
5. Original six checks: focus; Ruff on chunker/cli/tests with established
   exclusions; Black check on chunker/cli/tests/scripts; `scripts/mypy_gate.py`;
   `scripts/run_ci_smoke.py`; `scripts/run_platform_core.py --platform linux`.
   Use the locked all-extras environment, with toml for script tiers. Then
   locked refresh and actual full tests/spec_tests through run_full_suite.py,
   under private short TMPDIR `/mnt/workspace/worktrees/viperjuice/t466`.
   No percentage, performance or plan-output coverage gate; no type-baseline
   updates, parser-pin changes or hand-edited Boundary goldens.
6. Fresh exact-head Windows baseline/mutations/restorations/focus and unchanged
   standing preflight, all required hosted jobs, four manual tools-enabled CODE
   seats (Opus 5.5 subscription TUI, Gemini 3.8 Flash, Astra, Sol), and final
   supplemental Astra president. Compact file pointers; heartbeat only, no
   model/silence deadlines; max three complete substantive rounds, collect all
   four before reconciliation. Archive every frozen input and raw history before
   authorized exact-head merge, issue comment/closure and safe owned pruning.

## Acceptance criteria

- [ ] Real Python/JavaScript/TypeScript AST controls prove hidden expressions
  lie below configured ignored nodes. Both file APIs and metadata modes omit
  them, retain visible expressions and ancestor source text, and preserve exact
  declared content/spans/parents/routes/IDs. Ordinary string/comment controls
  are honest; real VFS streaming follows the same default boundary.
- [ ] Unchanged baseline and both named mutations fail the intended streaming
  boundary contracts, positive/regular controls remain, and exact restorations
  pass with current source/test/fixture/support bindings and retained visible
  tuple evidence. Documentation states the intended 6.0.0 removal without
  changing regular policy or claiming global API parity.
- [ ] Original six/refresh/full actual sealed zero exits, actual Windows stages
  and standing, exact hosted successes, four complete substantive agreements
  and supplemental Astra PROCEED qualify this repair only. All 61 canonical rows
  remain exact plus the own row; separate issues and protected state stay intact.

## Limits

Generic traversal honors each existing configured ignore predicate; representative
real contracts cover the three declared languages, not every grammar or span
transformation. Cache treesitter-chunker#358, Julia fixture treesitter-chunker#468
and CR-only policy treesitter-chunker#471 remain separate. No consumer locks,
admitted ledger/checkpoints, supplier/native-fill/IF, whole-phase or release
acceptance. Manual evidence is not agent-harness#1271's governed operational
amendment. All Unreleased changes remain reserved for 6.0.0; no tag.

## Execution notes

The unchanged baseline first fails 15 new streaming/API-parity/VFS cases with
six regular controls passing. Real AST checks pass in all three languages. An
initial Python fixture used a directly assigned/called lambda and triggered two
lint rules; that raw failed log is preserved. Its final fixture instead retains
the visible lambda in a tuple and interpolates the hidden lambda without calling
it. No lint suppression or production workaround is added. Initial fixture-byte
results are historical; final formatted fixtures receive fresh bound evidence.

On final source/test/fixture bytes, accepted production and both named mutations
each fail the intended 15 cases while six regular controls pass. Every exact
restoration passes all 21 new cases (35 existing module cases deselected).
Actual before/after snapshots cover twelve file API/metadata projections and
three in-memory VFS projections at the same paths. For each baseline and mutant,
regular tuples are unchanged; streaming/VFS remove exactly one hidden expression
and retain every other declared content/line/span/ID/parent/context/route tuple.
Ancestor chunks still include their entire source. This is retained per-API
evidence, not a global metadata-parity or arbitrary grammar claim.

The existing unnamed Ruby/Python guard, strict BAML and language-specific span
transformations remain intact. Both predicates are threaded through recursion;
the appended optional argument preserves the existing VFS positional call and
keeps any supplied chunk predicate when resolving the missing ignore predicate.
All 61 canonical manifest rows remain exact, plus this own executing row.

Fresh focused/original six/refresh/full, exact-head Windows mutation/restoration/
focus/standing, all required hosted checks, four substantive manual CODE R1
opinions and the final supplemental Astra chair remain required. Their actual
outcomes are recorded in immutable evidence and the acceptance comment rather
than changing the reviewed candidate later. No type-baseline update is made.
