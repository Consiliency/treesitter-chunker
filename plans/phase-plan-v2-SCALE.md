---
phase_loop_plan_version: 1
phase: SCALE
roadmap: specs/phase-plans-v2.md
roadmap_sha256: 177445a267e92f2ef1ae5c894bc426638f7fb3b106cec3824e13666f237ca788
---

# SCALE: Concurrency & Repo-Scale Correctness

## Context

The repo-scale/streaming defects, now fixable on the frozen IF-0-PARSER-1 (lease/thread-local),
IF-0-IDENTITY-1 (id-keyed maps), and IF-0-APISAFE-1 (confined vfs) contracts:
- Parser holders across the repo still cache a parser into a shared instance → the shared-parser
  segfault survives in `memory_pool.py`, `enhanced_chunker.py`, `performance/optimization/incremental.py`,
  `performance/optimization/batch.py`, `smart_context.py`, `export/relationships/tracker.py`,
  `repo/processor.py` (the PARSER-phase inventory in `docs/development/xfail-inventory.md`).
- `streaming.py` hardcodes Python-only node types → silent empty for Rust/Go/JS/Java.
- `multi_language.process_mixed_file` calls `chunk_file(file_path=…, content=…, language=…)` — a
  signature that doesn't exist → TypeError on every mixed file; `vfs_chunker` streaming breaks on
  Zip/HTTP and produces wrong/duplicated offsets.
- `parallel.py` timeout is dead code (`result(timeout=10)` on already-completed futures).
- `clustering/engine.py` `leidenalg.find_partition` has no seed → nondeterministic; `graph/cut.py`
  tie-order hash-randomized; `graph/xref.py` is O(n²·refs).
- `repo/processor.py` constructs a `git.Repo` + `check-ignore` subprocess per file, never `.close()`s,
  crashes on stale `last_commit` (`BadName`), and `watch_repository` busy-loops non-git dirs forever.

## Interface Freeze Gates
- [ ] IF-0-SCALE-1 — repo-scale correctness contract: NO code path shares a tree-sitter Parser across
  threads (all holders migrated to IF-0-PARSER-1); streaming yields correct chunks per-language or an
  explicit error (never silent empty); mixed-language + vfs paths call real signatures with correct
  file-relative offsets via the confined LocalFileSystem; `parallel.py` timeout actually stops a hung
  worker; Leiden is seeded and graph tie-order deterministic; `graph/xref` is index-based (no O(n²));
  git integration is leak-free with `BadName` fallback and a bounded watch loop.

## Lane Index & Dependencies

SL-1 — Parser-holder migration + parallel timeout
  Depends on: (none)
  Blocks: SL-7
  Parallel-safe: yes

SL-2 — streaming.py per-language node types
  Depends on: (none)
  Blocks: SL-7
  Parallel-safe: yes

SL-3 — multi_language + vfs_chunker
  Depends on: (none)
  Blocks: SL-7
  Parallel-safe: yes

SL-4 — clustering/graph determinism + xref index
  Depends on: (none)
  Blocks: SL-7
  Parallel-safe: yes

SL-5 — repo/processor git lifecycle + watch loop
  Depends on: (none)
  Blocks: SL-7
  Parallel-safe: no

SL-6 — performance incremental language fix
  Depends on: (none)
  Blocks: SL-7
  Parallel-safe: yes

SL-7 — Documentation & spec reconciliation (SL-docs)
  Depends on: SL-1, SL-2, SL-3, SL-4, SL-5, SL-6
  Blocks: (none)
  Parallel-safe: no

## Lanes

### SL-1 — Parser-holder migration + parallel timeout
- **Scope**: Migrate every cached-parser holder to the IF-0-PARSER-1 thread-local `get_parser`/`acquire_parser` (memory_pool, enhanced_chunker, batch, smart_context, tracker — the PARSER inventory, EXCEPT repo/processor.py which SL-5 owns); make `parallel.py` timeout actually cancel/stop a hung worker.
- **Owned files**: `chunker/performance/optimization/memory_pool.py`, `chunker/performance/optimization/batch.py`, `chunker/performance/enhanced_chunker.py`, `chunker/export/relationships/tracker.py`, `chunker/parallel.py`, `tests/test_scale_parser_holders.py`
- **Interfaces provided**: IF-0-SCALE-1 (no shared-parser holder; working parallel timeout)
- **Interfaces consumed**: IF-0-PARSER-1
- **Tasks**:

| Task ID | Type | Depends on | Files in scope | Tests owned | Test command |
|---|---|---|---|---|---|
| SL-1.1 | test | — | `tests/test_scale_parser_holders.py` | each migrated holder hands distinct parsers to distinct threads (no shared object); parallel.py timeout stops a worker that hangs beyond the deadline | `uv run --with toml --all-extras python -m pytest tests/test_scale_parser_holders.py -q` |
| SL-1.2 | impl | SL-1.1 | `chunker/performance/optimization/memory_pool.py`, `chunker/performance/optimization/batch.py`, `chunker/performance/enhanced_chunker.py`, `chunker/export/relationships/tracker.py` | — | — |
| SL-1.3 | impl | SL-1.2 | `chunker/parallel.py` | — | — |
| SL-1.4 | verify | SL-1.3 | holders + parallel | holder + parallel suite | `uv run --with toml --all-extras python -m pytest tests/test_scale_parser_holders.py tests/test_parallel.py -q` |

### SL-2 — streaming.py per-language node types
- **Scope**: Make `streaming.py` derive chunkable node types from the language-config registry (like `core._walk`), so non-Python languages yield correct chunks or an explicit error — never silent empty. If a streaming path can't be made correct, remove it and route to core.
- **Owned files**: `chunker/streaming.py`, `tests/test_streaming_languages.py`
- **Interfaces provided**: IF-0-SCALE-1 (streaming per-language correctness)
- **Interfaces consumed**: IF-0-PARSER-1
- **Tasks**:

| Task ID | Type | Depends on | Files in scope | Tests owned | Test command |
|---|---|---|---|---|---|
| SL-2.1 | test | — | `tests/test_streaming_languages.py` | streaming a Rust/Go/JS file yields the expected function/class chunks (not empty); an unsupported language raises an explicit error, not silent empty | `uv run --with toml --all-extras python -m pytest tests/test_streaming_languages.py -q` |
| SL-2.2 | impl | SL-2.1 | `chunker/streaming.py` | — | — |
| SL-2.3 | verify | SL-2.2 | streaming | streaming + existing streaming suite | `uv run --with toml --all-extras python -m pytest tests/test_streaming_languages.py tests/test_streaming.py -q` |

### SL-3 — multi_language + vfs_chunker
- **Scope**: Fix `multi_language.process_mixed_file` to call a real `chunk_file` signature; fix `vfs_chunker` streaming for Zip/HTTP backends with correct, non-duplicated, file-relative offsets, routing through APISAFE's confined `LocalFileSystem` (no sandbox re-open).
- **Owned files**: `chunker/multi_language.py`, `chunker/vfs_chunker.py`, `tests/test_multilang_vfs.py`
- **Interfaces provided**: IF-0-SCALE-1 (mixed-language + vfs correctness)
- **Interfaces consumed**: IF-0-APISAFE-1 (confined LocalFileSystem)
- **Tasks**:

| Task ID | Type | Depends on | Files in scope | Tests owned | Test command |
|---|---|---|---|---|---|
| SL-3.1 | test | — | `tests/test_multilang_vfs.py` | process_mixed_file on an HTML/MD/JSX file returns chunks (no TypeError); vfs streaming of a >10MB file (or a Zip-backed file) produces non-duplicated, file-relative offsets and stays within the confined root | `uv run --with toml --all-extras python -m pytest tests/test_multilang_vfs.py -q` |
| SL-3.2 | impl | SL-3.1 | `chunker/multi_language.py`, `chunker/vfs_chunker.py` | — | — |
| SL-3.3 | verify | SL-3.2 | multilang + vfs | multilang/vfs + existing suites | `uv run --with toml --all-extras python -m pytest tests/test_multilang_vfs.py -q` |

### SL-4 — clustering/graph determinism + xref index
- **Scope**: Seed `leidenalg.find_partition`; make `graph/cut.py` tie-order deterministic (sorted, on the version APISAFE froze); rewrite `graph/xref.py` to use a name→chunk index (no O(n²)) keyed on the frozen IF-0-IDENTITY-1 ids.
- **Owned files**: `chunker/clustering/engine.py`, `chunker/graph/xref.py`, `chunker/graph/cut.py`, `tests/test_scale_graph_determinism.py`
- **Interfaces provided**: IF-0-SCALE-1 (seeded Leiden, deterministic cut, indexed xref)
- **Interfaces consumed**: IF-0-IDENTITY-1
- **Tasks**:

| Task ID | Type | Depends on | Files in scope | Tests owned | Test command |
|---|---|---|---|---|---|
| SL-4.1 | test | — | `tests/test_scale_graph_determinism.py` | two Leiden runs on the same graph give identical clusters (seeded); graph/cut tie-order is deterministic across runs; xref on N chunks is index-based (no all-pairs) and edges key on IF-0-IDENTITY-1 ids | `uv run --with toml --all-extras python -m pytest tests/test_scale_graph_determinism.py -q` |
| SL-4.2 | impl | SL-4.1 | `chunker/clustering/engine.py`, `chunker/graph/xref.py`, `chunker/graph/cut.py` | — | — |
| SL-4.3 | verify | SL-4.2 | graph | graph determinism + xref/cut suites | `uv run --with toml --all-extras python -m pytest tests/test_scale_graph_determinism.py spec_tests/test_xref_graph.py spec_tests/test_graph_cut.py -q` |

### SL-5 — repo/processor git lifecycle + watch loop
- **Scope**: One `git.Repo` per operation with `.close()`; do NOT spawn `check-ignore` per file (batch or use pathspec); stale-commit `BadName` falls back to full scan; `watch_repository` has a stop condition and does not busy-loop non-git dirs. Route this file's parser use through IF-0-PARSER-1. This lane owns ALL `repo/processor.py` changes (single-writer).
- **Owned files**: `chunker/repo/processor.py`, `tests/test_repo_processor_lifecycle.py`
- **Interfaces provided**: IF-0-SCALE-1 (git lifecycle, bounded watch, BadName fallback)
- **Interfaces consumed**: IF-0-PARSER-1
- **Tasks**:

| Task ID | Type | Depends on | Files in scope | Tests owned | Test command |
|---|---|---|---|---|---|
| SL-5.1 | test | — | `tests/test_repo_processor_lifecycle.py` | a stale/nonexistent last_commit falls back to full scan (no BadName crash); processing does not spawn one check-ignore subprocess per file; watch_repository terminates on a stop signal and does not busy-loop a non-git dir | `uv run --with toml --all-extras python -m pytest tests/test_repo_processor_lifecycle.py -q` |
| SL-5.2 | impl | SL-5.1 | `chunker/repo/processor.py` | — | — |
| SL-5.3 | verify | SL-5.2 | repo | repo processor + existing repo suite | `uv run --with toml --all-extras python -m pytest tests/test_repo_processor_lifecycle.py -q` |

### SL-6 — performance incremental language fix
- **Scope**: Make `performance/optimization/incremental.py` use the tree's REAL language, not hardcoded `python`, and acquire its parser via IF-0-PARSER-1.
- **Owned files**: `chunker/performance/optimization/incremental.py`, `tests/test_perf_incremental_language.py`
- **Interfaces provided**: IF-0-SCALE-1 (real-language incremental reparse)
- **Interfaces consumed**: IF-0-PARSER-1
- **Tasks**:

| Task ID | Type | Depends on | Files in scope | Tests owned | Test command |
|---|---|---|---|---|---|
| SL-6.1 | test | — | `tests/test_perf_incremental_language.py` | incremental re-parse of a Rust/JS tree uses that language's grammar (not python) — produces a valid tree, not garbage | `uv run --with toml --all-extras python -m pytest tests/test_perf_incremental_language.py -q` |
| SL-6.2 | impl | SL-6.1 | `chunker/performance/optimization/incremental.py` | — | — |
| SL-6.3 | verify | SL-6.2 | perf incremental | perf incremental test | `uv run --with toml --all-extras python -m pytest tests/test_perf_incremental_language.py -q` |

### SL-7 — Documentation & spec reconciliation (SL-docs)
- **Scope**: Refresh the docs catalog, document the concurrency/repo-scale correctness contract, clear the PARSER-inventory holder entries in `docs/development/xfail-inventory.md` that SCALE migrated, and append post-execution amendments to the SCALE roadmap section if any freeze was wrong.
- **Owned files**: `README.md`, `docs/**`, `.claude/docs-catalog.json`, `docs/development/xfail-inventory.md`, `specs/phase-plans-v2.md`
- **Interfaces provided**: (none)
- **Interfaces consumed**: (none)
- **Parallel-safe**: no (terminal)
- **Depends on**: SL-1, SL-2, SL-3, SL-4, SL-5, SL-6

**Tasks**:

| Task ID | Type | Depends on | Files in scope | Action |
|---|---|---|---|---|
| SL-7.1 | docs | — | `.claude/docs-catalog.json` | Rescan via `scaffold_docs_catalog.py --rescan` (record "helper unavailable" if absent). |
| SL-7.2 | docs | SL-7.1 | `docs/**`, `README.md`, `docs/development/xfail-inventory.md` | Document the repo-scale/concurrency contract; mark the PARSER-inventory holder rows CLEARED (migrated by SCALE); append `SCALE` to `touched_by_phases`. |
| SL-7.3 | docs | SL-7.2 | `specs/phase-plans-v2.md` | Append `### Post-execution amendments` to the SCALE section if any freeze was empirically wrong. |
| SL-7.4 | verify | SL-7.3 | — | Run repo doc linters if configured; else no-op. |

## Execution Notes
- **Single-writer files**: `chunker/repo/processor.py` is owned EXCLUSIVELY by SL-5 (git lifecycle + watch + its parser migration) — SL-1's holder migration does NOT touch it. All other lanes own disjoint files. SL-7 (docs) owns `specs/phase-plans-v2.md` + `xfail-inventory.md` + docs.
- **Consumes the frozen contracts**: PARSER (IF-0-PARSER-1 lease/thread-local — the holder inventory in xfail-inventory.md is SCALE's worklist), IDENTITY (IF-0-IDENTITY-1 id-keyed xref), APISAFE (confined LocalFileSystem for vfs). This is why SCALE runs after all three.
- **Known destructive changes**: SL-2 may DELETE the broken streaming path if it can't be made per-language-correct (routing to core instead) — recorded here as the sole potential deletion; every other lane is in-place. 
- **Expected add/add conflicts**: none.
- **SL-0 re-exports**: n/a.
- **Stale-base guidance** (verbatim): Lane teammates in isolated worktrees do not see sibling merges automatically. If a lane finds its base is stale, it MUST stop and report rather than committing — the orchestrator will re-spawn or rebase. Silent `git reset --hard` or `git checkout HEAD~N -- …` in a stale worktree produces commits that destroy peer-lane work on `--no-ff` merge.

## Acceptance Criteria
- [ ] No code path shares a tree-sitter Parser across threads — every holder acquires via IF-0-PARSER-1 — proven by `tests/test_scale_parser_holders.py`; `parallel.py` timeout stops a hung worker.
- [ ] streaming yields correct per-language chunks (Rust/Go/JS) or an explicit error, never silent empty — proven by `tests/test_streaming_languages.py`.
- [ ] `process_mixed_file` returns chunks (no TypeError); vfs streaming has correct, non-duplicated, confined offsets — proven by `tests/test_multilang_vfs.py`.
- [ ] Leiden is seeded (identical clusters across runs); graph/cut tie-order deterministic; xref index-based, no O(n²) — proven by `tests/test_scale_graph_determinism.py`.
- [ ] Stale `last_commit` falls back to full scan (no BadName crash); no per-file check-ignore subprocess; watch loop bounded — proven by `tests/test_repo_processor_lifecycle.py`.
- [ ] `performance/optimization/incremental.py` uses the tree's real language — proven by `tests/test_perf_incremental_language.py`.

## Verification
```bash
uv run --with toml --all-extras python -m pytest tests/test_scale_parser_holders.py tests/test_streaming_languages.py tests/test_multilang_vfs.py tests/test_scale_graph_determinism.py tests/test_repo_processor_lifecycle.py tests/test_perf_incremental_language.py -q
uv run --with toml --all-extras python -m pytest tests/test_parallel.py tests/test_streaming.py spec_tests/test_xref_graph.py -q
```

## Spec Closeout Plan
- schema: `spec_delta_closeout.v1`
- decision: `no_spec_delta`
- target surfaces: `(none)`
- evidence paths: `logs/scale-streaming-determinism.txt`
- redaction posture: `metadata_only`
- downstream handling: `none`

## Execution Policy
- work-unit defaults: effort=high, reason=concurrency + repo-scale + determinism correctness is subtly wrong-prone
- SL-7: effort=low, reason=docs sweep only
