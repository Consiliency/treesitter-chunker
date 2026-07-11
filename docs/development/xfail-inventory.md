# Capped xfail inventory

> Maintainer/internal documentation. This page is intentionally omitted from
> public navigation and is enforced by the release-hygiene policy.

Only failures listed here may be quarantined. The cap is deliberately small so
the nightly suite remains an honest signal rather than a parking lot.

Maximum active xfails: 1

| Test | Reason | Clearing phase |
| --- | --- | --- |
| tests/integration/phase9/test_phase9_metadata_rules.py::test_docstring_extraction_with_rules | GATES-1: phase-9 docstring metadata baseline | COREFIX |

## mypy type-debt baseline (GATES)

Strict mypy carries **1241 pre-existing error signatures** (~2244 raw errors across ~214
files) surfaced when GATES removed the CI `::warning::` downgrade. CI runs
`scripts/mypy_gate.py`, a **baseline-relative** gate: it fails only on error signatures
NOT in `docs/development/mypy-baseline.txt`, so new type errors are blocked immediately
while the tracked debt is paid down by shrinking the baseline.

- Clearing owner: a dedicated type-debt phase (post-remediation), which reduces the
  baseline in bounded batches and re-runs `scripts/mypy_gate.py --update`.
- Do NOT add to the baseline to silence a new error — fix the error instead.

## PARSER holder inventory (complete) — migration owned by SCALE

PARSER delivered the safe primitive (thread-local `get_parser`, exclusive `acquire_parser`
lease) and migrated the holders it owns (`StreamingChunker`, plugin instances). Per the
roadmap PARSER exit criterion, EVERY remaining parser holder is inventoried here; per the
SCALE exit criterion ("All parser holders acquire via IF-0-PARSER-1; no shared-parser path
remains"), SCALE migrates each to the lease/thread-local API. Clearing owner: **SCALE**.

Thread-pool / pooled holders (MUST migrate — they store or pool a parser reused across threads):
- `chunker/performance/optimization/memory_pool.py:144` — pools the get_parser() result, then hands
  one pooled parser to concurrent checkouts (codex panel probe: `first is second == True`).
- `chunker/performance/enhanced_chunker.py` (warm_up ~:320) — pre-warms parsers into a shared pool.
- `chunker/performance/optimization/incremental.py:163` — caches parser per language in a shared dict.
- `chunker/smart_context.py:554` — caches parser per language in a shared instance dict.
- `chunker/export/relationships/tracker.py:112` — caches parser per language in a shared instance dict.
- `chunker/performance/optimization/batch.py` — thread-pool batch path (roadmap SCALE-named).
- `chunker/repo/processor.py` — ThreadPoolExecutor path (roadmap SCALE-named).

Interactive/single-thread holders (confirm-safe or migrate; low risk — not driven concurrently):
- `chunker/debug/visualization/ast_visualizer.py:31,37`, `chunker/debug/interactive/chunk_debugger.py:24`,
  `chunker/debug/interactive/node_explorer.py:43`, `chunker/debug/interactive/query_debugger.py:40`
  store `self.parser = get_parser(...)`; used by single-threaded interactive debug tools.

Do NOT treat this list as silenced — SCALE clears each entry by migrating it to `acquire_parser`/
thread-local `get_parser` and adding production-holder concurrency coverage.

## IDENTITY follow-up: overload edge disambiguation (owned by COREFIX)

IDENTITY made chunk_id/node_id collision-free (the #2 CRITICAL: no chunk is silently
dropped) and boundary node ids distinct for same-name overloads (stable ordinal). It also
made the boundary symbol index first-wins so a later overload can no longer silently steal
ALL edges from the first.

What remains (panel: codex/gemini): NAME-based edge resolution cannot determine WHICH
overload a call `foo(...)` targets — that needs signature/type resolution. So an edge to an
overloaded name resolves deterministically to the first declaration, and genuinely-external
references stay `unresolved`. Correctly attributing an overload call to its matching
signature is semantic-resolution work owned by **COREFIX** (the roadmap defers a mandatory
semantic resolver). Clearing owner: COREFIX. This does NOT drop chunks and does NOT leave
edges pointing at non-nodes for resolvable references.
