---
phase_loop_plan_version: 1
phase: COREFIX
roadmap: specs/phase-plans-v2.md
roadmap_sha256: 177445a267e92f2ef1ae5c894bc426638f7fb3b106cec3824e13666f237ca788
---

# COREFIX: Core Chunk Correctness

## Context

The review's per-chunk correctness cluster, now fixable against the frozen IF-0-IDENTITY-1 contract:
- `incremental.py` content-diff reparses with `file_path=""` while old chunk ids embed the real path,
  so no id ever matches → every edit reports all-ADDED + all-DELETED; MODIFIED is structurally dead.
- `auto.py:227,298,379` fallback catches narrow/wrong exception tuples (`(OSError,FileNotFoundError,
  IndexError)` / `(IndexError,KeyError)`), missing `LanguageNotFoundError`/`ParserError`, so the
  zero-config API crashes instead of falling back; `chunker.py` reads strict UTF-8.
- `core.py` dead `end_line` conditional gives span-extended chunks (Dart sig+body, R) line ranges
  inconsistent with bytes; Svelte control-flow chunks emitted 2–3×; `_walk` has no recursion guard.
- `token/chunker.py` split sub-chunks inherit `byte_start=original.byte_start`; fallback chunkers
  store CHARACTER offsets in `byte_*` and do O(n²) `content[:idx].count("\n")` per chunk.
- `smart_context.py` caches by `(chunk_id, type)` while the result depends on the `chunks` arg (not
  in key) → stale cross-repo results; O(n²) all-pairs feature extraction.

IDENTITY made ids collision-free and stable, so incremental MODIFIED can now key on `definition_id`.
COREFIX also inherits the overload-edge-semantic follow-up scoped to it (docs/development/xfail-inventory.md).

## Interface Freeze Gates
- [ ] IF-0-COREFIX-1 — per-chunk correctness contract: incremental diff reparses with the real
  `file_path` and classifies body edits as MODIFIED via `definition_id`; fallback catches the real
  failure types and falls back (no crash); span-extended chunks have byte-consistent line ranges;
  Svelte control-flow chunks emitted once; token/fallback chunks carry TRUE byte offsets (not char);
  `smart_context` cache key includes the candidate set and the O(n²) pass is bounded/indexed; `_walk`
  degrades to fallback on deep recursion instead of `RecursionError`.

## Lane Index & Dependencies

SL-1 — Incremental diff via definition_id
  Depends on: (none)
  Blocks: SL-6
  Parallel-safe: yes

SL-2 — Fallback robustness + encoding
  Depends on: (none)
  Blocks: SL-6
  Parallel-safe: yes

SL-3 — core.py end_line + Svelte + recursion guard
  Depends on: (none)
  Blocks: SL-6
  Parallel-safe: no

SL-4 — Token split offsets
  Depends on: (none)
  Blocks: SL-6
  Parallel-safe: yes

SL-5 — Fallback byte offsets + smart_context cache/O(n2)
  Depends on: (none)
  Blocks: SL-6
  Parallel-safe: yes

SL-6 — Documentation & spec reconciliation (SL-docs)
  Depends on: SL-1, SL-2, SL-3, SL-4, SL-5
  Blocks: (none)
  Parallel-safe: no

## Lanes

### SL-1 — Incremental diff via definition_id
- **Scope**: Reparse with the real `file_path`, and classify true body edits as MODIFIED by keying on the stable `definition_id` (IF-0-IDENTITY-1) instead of content-bearing chunk_id.
- **Owned files**: `chunker/incremental.py`, `tests/test_incremental_diff.py`
- **Interfaces provided**: IF-0-COREFIX-1 (incremental MODIFIED via definition_id)
- **Interfaces consumed**: (none)
- **Tasks**:

| Task ID | Type | Depends on | Files in scope | Tests owned | Test command |
|---|---|---|---|---|---|
| SL-1.1 | test | — | `tests/test_incremental_diff.py` | a one-line body edit produces a MINIMAL diff (1 MODIFIED, not all-ADDED + all-DELETED); reparse uses the real path so ids match | `uv run --with toml --all-extras python -m pytest tests/test_incremental_diff.py -q` |
| SL-1.2 | impl | SL-1.1 | `chunker/incremental.py` | — | — |
| SL-1.3 | verify | SL-1.2 | incremental | diff + existing incremental suite | `uv run --with toml --all-extras python -m pytest tests/test_incremental_diff.py tests/test_incremental.py -q` |

### SL-2 — Fallback robustness + encoding
- **Scope**: Make fallback catch the actual failure types (`LanguageNotFoundError`, `ParserError`, …) so the zero-config API falls back instead of crashing; make file reads use `errors="replace"` where core does.
- **Owned files**: `chunker/auto.py`, `chunker/chunker.py`, `tests/test_fallback_robustness.py`
- **Interfaces provided**: IF-0-COREFIX-1 (fallback catches real failure types)
- **Interfaces consumed**: (none)
- **Tasks**:

| Task ID | Type | Depends on | Files in scope | Tests owned | Test command |
|---|---|---|---|---|---|
| SL-2.1 | test | — | `tests/test_fallback_robustness.py` | a grammar-load failure (LanguageNotFoundError/ParserError) makes auto_chunk fall back (fallback_used=True) instead of raising; a file with invalid UTF-8 bytes chunks via errors=replace, no crash | `uv run --with toml --all-extras python -m pytest tests/test_fallback_robustness.py -q` |
| SL-2.2 | impl | SL-2.1 | `chunker/auto.py`, `chunker/chunker.py` | — | — |
| SL-2.3 | verify | SL-2.2 | fallback | robustness + auto suite | `uv run --with toml --all-extras python -m pytest tests/test_fallback_robustness.py tests/test_auto.py -q` |

### SL-3 — core.py end_line + Svelte + recursion guard
- **Scope**: Fix the dead `end_line` conditional so span-extended chunks (Dart sig+body, R) report line ranges consistent with their bytes; emit Svelte control-flow chunks once; add a `_walk` recursion-depth guard that degrades to fallback instead of `RecursionError`.
- **Owned files**: `chunker/core.py`, `tests/test_core_span_consistency.py`
- **Interfaces provided**: IF-0-COREFIX-1 (span/line consistency, single Svelte CF emit, recursion guard)
- **Interfaces consumed**: (none)
- **Tasks**:

| Task ID | Type | Depends on | Files in scope | Tests owned | Test command |
|---|---|---|---|---|---|
| SL-3.1 | test | — | `tests/test_core_span_consistency.py` | a span-extended chunk's end_line matches its byte range; a Svelte file with one script + template emits each control-flow chunk ONCE; deeply-nested input degrades to fallback (no RecursionError) | `uv run --with toml --all-extras python -m pytest tests/test_core_span_consistency.py -q` |
| SL-3.2 | impl | SL-3.1 | `chunker/core.py` | — | — |
| SL-3.3 | verify | SL-3.2 | core | span + chunking + svelte | `uv run --with toml --all-extras python -m pytest tests/test_core_span_consistency.py tests/test_chunking.py tests/test_svelte_language.py -q` |

### SL-4 — Token split offsets
- **Scope**: Give token split sub-chunks correct `byte_start` / `byte_end` / `start_line` (not the original's), so offsets on split parts map back to the file.
- **Owned files**: `chunker/token/chunker.py`, `tests/test_token_split_offsets.py`
- **Interfaces provided**: IF-0-COREFIX-1 (token split offset correctness)
- **Interfaces consumed**: (none)
- **Tasks**:

| Task ID | Type | Depends on | Files in scope | Tests owned | Test command |
|---|---|---|---|---|---|
| SL-4.1 | test | — | `tests/test_token_split_offsets.py` | splitting a large function into N parts: each part's byte_start/byte_end slice back to that part's content in the original; start_line is correct | `uv run --with toml --all-extras python -m pytest tests/test_token_split_offsets.py -q` |
| SL-4.2 | impl | SL-4.1 | `chunker/token/chunker.py` | — | — |
| SL-4.3 | verify | SL-4.2 | token | split offsets + token suite | `uv run --with toml --all-extras python -m pytest tests/test_token_split_offsets.py -q` |

### SL-5 — Fallback byte offsets + smart_context cache/O(n2)
- **Scope**: Make fallback chunkers store TRUE byte offsets (not character offsets) in `byte_*` with no per-chunk O(n²) newline scan; fix `smart_context` to include the candidate set in the cache key and replace the O(n²) all-pairs feature extraction with a bounded/indexed approach.
- **Owned files**: `chunker/fallback/`, `chunker/fallback_overlap/`, `chunker/smart_context.py`, `tests/test_fallback_offsets_smartctx.py`
- **Interfaces provided**: IF-0-COREFIX-1 (fallback byte offsets, smart_context cache key + bounded pass)
- **Interfaces consumed**: (none)
- **Tasks**:

| Task ID | Type | Depends on | Files in scope | Tests owned | Test command |
|---|---|---|---|---|---|
| SL-5.1 | test | — | `tests/test_fallback_offsets_smartctx.py` | on a non-ASCII (multibyte) file, fallback chunk byte_start/byte_end slice the FILE BYTES back to the chunk content; smart_context returns different results for different candidate sets (cache key includes candidates); large input does not do all-pairs O(n²) | `uv run --with toml --all-extras python -m pytest tests/test_fallback_offsets_smartctx.py -q` |
| SL-5.2 | impl | SL-5.1 | `chunker/fallback/`, `chunker/fallback_overlap/`, `chunker/smart_context.py` | — | — |
| SL-5.3 | verify | SL-5.2 | fallback + smartctx | offsets + fallback + smart_context suites | `uv run --with toml --all-extras python -m pytest tests/test_fallback_offsets_smartctx.py tests/test_fallback_chunking.py -q` |

### SL-6 — Documentation & spec reconciliation (SL-docs)
- **Scope**: Refresh the docs catalog, document the per-chunk correctness fixes, and append post-execution amendments to the COREFIX roadmap section if any freeze was wrong.
- **Owned files**: `README.md`, `docs/**`, `.claude/docs-catalog.json`, `specs/phase-plans-v2.md`
- **Interfaces provided**: (none)
- **Interfaces consumed**: (none)
- **Parallel-safe**: no (terminal)
- **Depends on**: SL-1, SL-2, SL-3, SL-4, SL-5

**Tasks**:

| Task ID | Type | Depends on | Files in scope | Action |
|---|---|---|---|---|
| SL-6.1 | docs | — | `.claude/docs-catalog.json` | Rescan via `scaffold_docs_catalog.py --rescan` (record "helper unavailable" if absent). |
| SL-6.2 | docs | SL-6.1 | `docs/**`, `README.md` | Document the incremental-diff/fallback/span/offset/smart_context fixes; append `COREFIX` to `touched_by_phases`. |
| SL-6.3 | docs | SL-6.2 | `specs/phase-plans-v2.md` | Append `### Post-execution amendments` to the COREFIX section if any freeze was empirically wrong. |
| SL-6.4 | verify | SL-6.3 | — | Run repo doc linters if configured; else no-op. |

## Execution Notes
- **Single-writer files**: `chunker/core.py` is owned exclusively by **SL-3** (end_line + Svelte + recursion guard are one coherent change). SL-1 owns `incremental.py`, SL-2 owns `auto.py`+`chunker.py`, SL-4 owns `token/chunker.py`, SL-5 owns `fallback/`+`fallback_overlap/`+`smart_context.py` — all disjoint. SL-6 (docs) owns `specs/phase-plans-v2.md` + docs. COREFIX does NOT edit `__init__.py` (the public `chunk_text` in-memory fix is IFACE's).
- **Known destructive changes**: none — in-place correctness edits + additive tests. No file deletions.
- **Expected add/add conflicts**: none.
- **SL-0 re-exports**: n/a.
- **Stale-base guidance** (verbatim): Lane teammates in isolated worktrees do not see sibling merges automatically. If a lane finds its base is stale, it MUST stop and report rather than committing — the orchestrator will re-spawn or rebase. Silent `git reset --hard` or `git checkout HEAD~N -- …` in a stale worktree produces commits that destroy peer-lane work on `--no-ff` merge.
- **Consumes IDENTITY**: incremental MODIFIED classification keys on `definition_id` (frozen IF-0-IDENTITY-1); this is why COREFIX runs after IDENTITY.
- **Inherited follow-up (out of scope, tracked)**: overload edge disambiguation (signature-aware) is recorded in `docs/development/xfail-inventory.md` as COREFIX-owned; address if in scope, else keep the tracked deferral.

## Acceptance Criteria
- [ ] A one-line body edit yields a minimal incremental diff (1 MODIFIED via definition_id), not all-ADDED/all-DELETED — proven by `tests/test_incremental_diff.py`.
- [ ] A grammar-load failure makes the zero-config API fall back (not crash); invalid-UTF-8 files chunk via errors=replace — proven by `tests/test_fallback_robustness.py`.
- [ ] Span-extended chunks report byte-consistent line ranges; Svelte control-flow chunks emit once; deep nesting degrades to fallback (no RecursionError) — proven by `tests/test_core_span_consistency.py`.
- [ ] Token split sub-chunks' byte offsets slice back to their content — proven by `tests/test_token_split_offsets.py`.
- [ ] Fallback chunks store true byte offsets on multibyte files; smart_context cache key includes the candidate set; the all-pairs O(n²) pass is bounded — proven by `tests/test_fallback_offsets_smartctx.py`.

## Verification
```bash
uv run --with toml --all-extras python -m pytest tests/test_incremental_diff.py tests/test_fallback_robustness.py tests/test_core_span_consistency.py tests/test_token_split_offsets.py tests/test_fallback_offsets_smartctx.py -q
uv run --with toml --all-extras python -m pytest tests/test_chunking.py tests/test_auto.py tests/test_incremental.py tests/test_fallback_chunking.py -q
```

## Spec Closeout Plan
- schema: `spec_delta_closeout.v1`
- decision: `no_spec_delta`
- target surfaces: `(none)`
- evidence paths: `logs/corefix-tests.txt`
- redaction posture: `metadata_only`
- downstream handling: `none`

## Execution Policy
- work-unit defaults: effort=high, reason=per-chunk offset/diff/span correctness is subtly wrong-prone and byte-exact
- SL-6: effort=low, reason=docs sweep only
