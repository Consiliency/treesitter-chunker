---
phase_loop_plan_version: 1
phase: PARSER
roadmap: specs/phase-plans-v2.md
roadmap_sha256: 177445a267e92f2ef1ae5c894bc426638f7fb3b106cec3824e13666f237ca788
---

# PARSER: Parser Concurrency Safety

## Context

The review's #1 CRITICAL: `chunker/_internal/factory.py` `get_parser()` (line 239-242) returns the
same LRU-cached `tree_sitter.Parser` to every caller without removing it, and on a pool hit
(244-248) it ALSO `_cache.put`s that instance — so N concurrent callers receive the SAME parser
object. `chunker/parser.py`'s module-level `get_parser()` exposes this shared object directly, and
`repo/processor.py` (SCALE) drives it from a `ThreadPoolExecutor`. Since `tree_sitter.Parser.parse()`
releases the GIL for the C parse, concurrent `.parse()` on one object is undefined behavior —
corrupted trees or a native segfault. The container locks (`LRUCache.lock`, `ParserPool.lock`,
`ParserFactory._lock`) guard only the containers, never the dispensed parser; there is no checkout.

PARSER makes parser acquisition safe by construction: an exclusive lease/checkout API and a public
`get_parser()` that never hands the same live parser to two threads (thread-local ownership). This
freezes IF-0-PARSER-1, which SCALE consumes to fix every thread-pool path. The phase is bounded to
`chunker/_internal/factory.py` + `chunker/parser.py` (+ tests); the ~10 holder call sites keep the
same `get_parser(language) -> Parser` signature, so they need no change — they simply become safe.

## Interface Freeze Gates
- [ ] IF-0-PARSER-1 — `acquire_parser(language, config=None) -> ParserLease` where `ParserLease` is
  a context manager (`__enter__ -> Parser`, `__exit__` returns it) holding a parser EXCLUSIVELY for
  the lease's lifetime (removed from the shared cache/pool while leased; no object ever in cache and
  pool simultaneously); AND a public `get_parser(language) -> Parser` that is safe by construction
  (thread-local per (thread, language)) so no raw parser is shared across threads. Exposed from
  `chunker.parser` and `chunker._internal.factory`.

## Lane Index & Dependencies

SL-1 — Lease API + thread-safe factory
  Depends on: (none)
  Blocks: SL-2, SL-3
  Parallel-safe: no

SL-2 — Concurrency stress test
  Depends on: SL-1
  Blocks: SL-3
  Parallel-safe: yes

SL-3 — Documentation & spec reconciliation (SL-docs)
  Depends on: SL-1, SL-2
  Blocks: (none)
  Parallel-safe: no

## Lanes

### SL-1 — Lease API + thread-safe factory
- **Scope**: Add `acquire_parser()` exclusive-lease checkout (no object in cache and pool at once), make the public `get_parser()` thread-local safe-by-construction, and lock the cold-miss create/put + fix the wrong exception tuples flagged by the review.
- **Owned files**: `chunker/_internal/factory.py`, `chunker/parser.py`, `tests/test_parser_lease.py`
- **Interfaces provided**: IF-0-PARSER-1 (`acquire_parser`, `ParserLease`, thread-local `get_parser`)
- **Interfaces consumed**: (none)
- **Tasks**:

| Task ID | Type | Depends on | Files in scope | Tests owned | Test command |
|---|---|---|---|---|---|
| SL-1.1 | test | — | `tests/test_parser_lease.py` | `acquire_parser` yields an exclusive parser removed from cache/pool while leased; two `get_parser(lang)` from different threads return DISTINCT objects; same thread reuses its thread-local; no object in cache+pool at once | `uv run --with toml --all-extras python -m pytest tests/test_parser_lease.py -q` |
| SL-1.2 | impl | SL-1.1 | `chunker/_internal/factory.py` | — | — |
| SL-1.3 | impl | SL-1.2 | `chunker/parser.py` | — | — |
| SL-1.4 | verify | SL-1.3 | factory + parser | lease tests + import | `uv run --with toml --all-extras python -m pytest tests/test_parser_lease.py -q && uv run python -c "import chunker; from chunker.parser import get_parser, acquire_parser"` |

### SL-2 — Concurrency stress test
- **Scope**: Prove the fix under load — N threads × many parses over the public API and the lease API produce no corrupted trees / crash across repeated runs.
- **Owned files**: `tests/test_parser_concurrency_stress.py`
- **Interfaces provided**: (none)
- **Interfaces consumed**: IF-0-PARSER-1 (`acquire_parser`, thread-local `get_parser`)
- **Tasks**:

| Task ID | Type | Depends on | Files in scope | Tests owned | Test command |
|---|---|---|---|---|---|
| SL-2.1 | test | — | `tests/test_parser_concurrency_stress.py` | 16 threads × 200 parses via `get_parser` and via `acquire_parser` produce well-formed trees with expected node counts, repeated 3× with no exception/crash | `uv run --with toml --all-extras python -m pytest tests/test_parser_concurrency_stress.py -q` |
| SL-2.2 | verify | SL-2.1 | stress test | stress green | `uv run --with toml --all-extras python -m pytest tests/test_parser_concurrency_stress.py -q` |

### SL-3 — Documentation & spec reconciliation (SL-docs)
- **Scope**: Refresh the docs catalog, document the parser lease/thread-local concurrency contract, and append post-execution amendments to the PARSER roadmap section if any freeze was empirically wrong.
- **Owned files**: `README.md`, `docs/performance-guide/**`, `.claude/docs-catalog.json`, `specs/phase-plans-v2.md`
- **Interfaces provided**: (none)
- **Interfaces consumed**: (none)
- **Parallel-safe**: no (terminal)
- **Depends on**: SL-1, SL-2

**Tasks**:

| Task ID | Type | Depends on | Files in scope | Action |
|---|---|---|---|---|
| SL-3.1 | docs | — | `.claude/docs-catalog.json` | Rescan via `scaffold_docs_catalog.py --rescan` (record "helper unavailable" if absent). |
| SL-3.2 | docs | SL-3.1 | `README.md`, `docs/performance-guide/**` | Document the `acquire_parser` lease + thread-local `get_parser` concurrency contract; append `PARSER` to `touched_by_phases`. |
| SL-3.3 | docs | SL-3.2 | `specs/phase-plans-v2.md` | Append `### Post-execution amendments` to the PARSER section if any freeze was empirically wrong. |
| SL-3.4 | verify | SL-3.3 | — | Run repo doc linters if configured; else no-op. |

## Execution Notes
- **Single-writer files**: `chunker/_internal/factory.py` and `chunker/parser.py` are owned exclusively by **SL-1** (the lease API + thread-local rework is one coherent change; they cannot be split without contending). SL-2 owns only its stress-test file; SL-3 (docs) owns disjoint doc paths + `specs/phase-plans-v2.md`.
- **Backward compatibility**: the ~10 holder call sites (`auto.py`, `multi_language.py`, `streaming.py`, `__init__.py`, `debug/**`, `plugin_manager.py`, `performance/optimization/incremental.py`) keep calling `get_parser(language) -> Parser`; SL-1 must preserve that signature so they need no edit — they become safe transparently. `return_parser()` remains valid (no-op-safe) for any caller still using it.
- **Known destructive changes**: none — every change is in-place in factory.py/parser.py or an additive test.
- **Expected add/add conflicts**: none.
- **SL-0 re-exports**: n/a.
- **Stale-base guidance** (verbatim): Lane teammates in isolated worktrees do not see sibling merges automatically. If SL-2 finds its base is pre-SL-1, it MUST stop and report rather than committing — the orchestrator will re-spawn or rebase. Silent `git reset --hard` or `git checkout HEAD~N -- …` in a stale worktree produces commits that destroy peer-lane work on `--no-ff` merge.

## Acceptance Criteria
- [ ] `acquire_parser(lang)` yields a parser removed from the shared cache/pool for the lease's lifetime and returned on exit; no parser object is ever in cache and pool simultaneously — proven by `tests/test_parser_lease.py`.
- [ ] Two `get_parser(lang)` calls from different threads return DISTINCT objects; a single thread reuses its own thread-local — proven by `tests/test_parser_lease.py`.
- [ ] 16 threads × 200 parses via both `get_parser` and `acquire_parser`, repeated 3×, produce well-formed trees with no exception/crash — proven by `tests/test_parser_concurrency_stress.py`.
- [ ] `import chunker` and the ~10 holder modules still import and chunk correctly (unchanged `get_parser` signature) — proven by `uv run python -c "import chunker; from chunker.parser import get_parser, acquire_parser"` + the existing chunking test batch.

## Verification
```bash
uv run --with toml --all-extras python -m pytest tests/test_parser_lease.py tests/test_parser_concurrency_stress.py -q
uv run python -c "import chunker; from chunker.parser import get_parser, acquire_parser; print('lease API exported')"
uv run --with toml --all-extras python -m pytest tests/test_chunking.py tests/test_parser.py tests/test_factory.py -q
```

## Spec Closeout Plan
- schema: `spec_delta_closeout.v1`
- decision: `no_spec_delta`
- target surfaces: `(none)`
- evidence paths: `logs/parser-stress-test.txt`
- redaction posture: `metadata_only`
- downstream handling: `none`

## Execution Policy
- work-unit defaults: effort=high, reason=concurrency correctness with tree-sitter GIL-releasing parse is subtly wrong-prone
- SL-3: effort=low, reason=docs sweep only
