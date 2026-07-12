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

Thread-pool / pooled holders — **CLEARED by SCALE** (migrated to thread-local `get_parser`;
no code path now shares one Parser across threads — proven by `tests/test_scale_parser_holders.py`):
- `chunker/performance/optimization/memory_pool.py` — CLEARED (SL-1): `acquire("parser:*")` now
  short-circuits to thread-local `get_parser`; parsers are never pooled/re-checked-out across threads.
- `chunker/performance/enhanced_chunker.py` — CLEARED (SL-1): `_parse_file` acquires per-thread; the
  parser warm-up pool path is a no-op.
- `chunker/performance/optimization/incremental.py` — CLEARED (SL-6): removed the shared
  `_parser_cache`; each re-parse acquires the tree's real-language parser via thread-local `get_parser`.
- `chunker/smart_context.py` — CLEARED (SCALE closeout): `_get_parser` returns thread-local
  `get_parser(language)` on every call; the shared `self._parsers` dict was removed. (This holder was
  named in the SL-1 scope prose but omitted from the SL-1 owned-files list — migrated at SCALE
  closeout to satisfy the exit criterion.)
- `chunker/export/relationships/tracker.py` — CLEARED (SL-1): removed `self._parsers`; `_get_parser`
  returns thread-local `get_parser`.
- `chunker/performance/optimization/batch.py` — CLEARED (SL-1): the ThreadPoolExecutor batch path
  acquires per-thread via `get_parser`.
- `chunker/repo/processor.py` — CLEARED (SL-5): delegates all parsing to the thread-local `get_parser`
  via the Chunker adapter; holds no Parser.

Interactive/single-thread holders (confirm-safe — not driven concurrently; left as-is):
- `chunker/debug/visualization/ast_visualizer.py:31,37`, `chunker/debug/interactive/chunk_debugger.py:24`,
  `chunker/debug/interactive/node_explorer.py:43`, `chunker/debug/interactive/query_debugger.py:40`
  store `self.parser = get_parser(...)`; used by single-threaded interactive debug tools. These are not
  a concurrency hazard (never driven from multiple threads); documented as confirm-safe, not migrated.

SCALE outcome: every production/thread-pool parser holder now acquires via IF-0-PARSER-1
thread-local `get_parser`; no shared-parser path remains on any concurrent code path.

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

## COREFIX follow-up: fallback-path residuals (panel-found, tracked)

The COREFIX iteration-3 merge panel (codex red-team leg) surfaced three real,
PRE-EXISTING defects in the fallback / identity paths. They are OUTSIDE the
class-split contract fix that was the merge subject (which all four panel legs
confirmed correct) and outside COREFIX's stated acceptance-criteria tests (all
passing). They are tracked here for a dedicated follow-up (candidate: fold into
SCALE, which already touches identity-keyed maps and fallback, or a RELEASE-gate
fix). Verified real by direct probe/inspection on 2026-07-11.

1. **Fallback `definition_id` collision (identity contract).**
   `chunker/core.py:1171` assigns fallback chunks
   `compute_definition_id(file_path, language, qualified_route or parent_route)`.
   Fallback chunks have EMPTY routes, so every fallback chunk in a file receives
   the SAME `definition_id`. `chunker/incremental.py` keys MODIFIED/ADDED/DELETED
   classification on `definition_id`, so multiple fallback chunks collapse into
   one identity and incremental diffs lose chunks. Fix direction: give routeless
   chunks a disambiguating route component (e.g. byte_start or an ordinal) in the
   definition_id derivation, mirroring the IDENTITY node_id seed.

2. **CSV fallback slice-back violation (byte-offset contract).**
   `chunker/fallback/strategies/line_based.py` `_chunk_csv` with
   `include_header=True` prepends the header row to every chunk after the first
   (`chunk_lines.append(header)`), but computes `byte_start/byte_end` from the
   data-row spans only (`lines[:i]`..`lines[:chunk_end]`). So
   `src[byte_start:byte_end]` slices back the data rows WITHOUT the prepended
   header, contradicting the README universal slice-back contract (which names
   fallback chunks). This is the same defect class fixed for class token-splits
   in COREFIX (commit a0ab4fea). Fix direction (Model-1): keep content = the
   contiguous data-row slice and preserve the CSV header in `parent_context` /
   `metadata["csv_header"]`, OR extend the span to include the header bytes (not
   possible contiguously — Model-1 is the correct resolution).

3. **Fallback O(n²) prefix rescans (performance).**
   `chunker/fallback/base.py` (`chunk_by_lines` ~:186) and
   `chunker/fallback/strategies/line_based.py` (~:152) recompute
   `sum(len(line) for line in lines[:i])` / re-join every preceding line for each
   chunk, an O(n²) offset scan. COREFIX's O(n²) exit criterion was scoped to and
   satisfied for `smart_context` (the all-pairs similarity pass, now O(n·cap));
   this fallback prefix-scan is a separate, lower-severity performance residual.
   Fix direction: carry a running byte cursor (the `TextPositionIndex` already
   built) instead of re-summing prefixes.

## SCALE follow-up: streaming special-case node adjustments (panel-found, tracked)

SL-2 made `chunker/streaming.py` derive its chunkable-node PREDICATE per-language
from the shared `core.resolve_chunk_predicates`, so streaming now matches
non-streaming `chunk_file` node selection for mainstream languages
(Python/Go/Rust/JS/TS/Java/C/C++/Ruby/C#) — spans and ids identical (proven by
`tests/test_spans_roundtrip.py` + `tests/test_streaming_languages.py`).

What streaming does NOT yet replicate (Fable SCALE panel finding): `core._walk`'s
per-language span/node-type ADJUSTMENTS applied AFTER selection —
- Dart: `*_signature` → `*_declaration` rename + signature+body span merge
  (streamed chunk is `method_signature` bytes 14–35; `chunk_file` is
  `method_declaration` bytes 14–59, so node_type/byte_end/node_id differ).
- R: `setClass`/`setMethod`/`setGeneric` `call` force-chunk.
- Elixir: `call` reinterpretation.
- Svelte: control-flow chunk synthesis.

For these four languages a STREAMED chunk's node_type/span (hence node_id) can
diverge from `chunk_file`. This is a strict improvement over the prior
silent-empty streaming output (which yielded NOTHING for any non-Python
language), not a regression. Fix direction: factor `_walk`'s post-selection
adjustment pass into a shared helper (like `resolve_chunk_predicates`) and apply
it in the streaming walk, OR route these four languages' streaming through
`core.chunk_file`. Not blocking: mainstream-language streaming is exact, and the
divergence never drops chunks — it only changes span granularity for 4 langs.

## IFACE residual: CLI-stack + parquet-exporter consolidation (internal, low-risk)

IFACE closed 4 of its 6 exit criteria with tests — the ones with downstream
consumer impact or correctness bugs:
- shared detection map (`.ts`→typescript everywhere; unknown-ext warns) — DONE.
- gzip.Path→gzip.open so `compress=True` works — DONE + tested.
- public `chunk_text` in-memory (deterministic node_ids, no temp round-trip) — DONE + tested.
- version single-sourced (pyproject 3.2.2; `__init__` fallback + `_version.py` corrected) — DONE + tested.

Two exit criteria remain as tracked INTERNAL refactors — the sister-repo scan
proved NO external consumer invokes either CLI stack (`cli/` or `chunker/cli/`)
or imports `chunker.exporters.parquet` (only `tests/test_parquet_export.py`
does), so these are cosmetic-consolidation, not correctness or compatibility:

1. **CLI stack consolidation.** Two stacks coexist: `cli/` (main.py + repo/setup/
   debug commands) and `chunker/cli/` (grammar/cluster/symbol commands, the
   packaged `__main__`). The exit criterion wants one to own grammar-management/
   resolution-mode defaults/flag conventions and the other to thinly delegate.
   Deferred because it is a pure internal refactor with real regression surface
   and zero external blast radius; safest as its own focused change with the CLI
   integration tests run, not rushed. Any `-o` / `--resolution-mode` default
   divergence should be reconciled there.
2. **Parquet exporter split.** `chunker/exporters/parquet.py` (`ParquetExporter`,
   standalone chunks-only, columns/partition_by) vs
   `chunker/export/formats/parquet.py` (`StructuredExporter` subclass, chunks +
   relationships). They serve different shapes; "resolving" the split means
   picking one schema authority or a shared schema helper. Deferred: only the
   test imports the standalone one; the framework one is the registered format.

Neither blocks RELEASE correctness; both are follow-up hygiene.
