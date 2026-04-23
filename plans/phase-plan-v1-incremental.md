# INCREMENTAL: Incremental Boundary Recompute

## Context

Roadmap source: `specs/phase-plans-v1.md`, Phase 5. The roadmap file is tracked and clean, so it is not an untracked `git clean -fd` risk.

Phase 1 through Phase 4 artifacts are present in this working tree. `chunker.boundary.extract_boundary_ir()` emits canonical Boundary IR from `chunk_file(..., extract_metadata=True, include_retrieval_metadata=True)` and `extract_symbol_graph()`. `docs/interface-boundary-spec.md` now freezes schema, resolution, conformance, metrics, diagnostics, `fail_fast`, and opt-in timings. Existing caches are AST/chunk oriented (`chunker/_internal/cache.py`, `chunker/performance/cache/manager.py`, `chunker/incremental.py`) and do not preserve Boundary IR records keyed by schema, grammar/tool version, resolution mode, and extraction options.

The Phase 5 plan must keep canonical JSON output byte-identical between cold and warm runs. Cache hit/miss details, recomputed path sets, and benchmark measurements are implementation diagnostics, not canonical Boundary IR fields. Default non-incremental behavior and existing golden snapshots should remain stable unless a test exposes a real Phase 5 contract bug.

## Interface Freeze Gates

- [ ] IF-0-INCREMENTAL-6 -- Boundary cache key format, warm-run invalidation rules, and impacted-neighbor recomputation contract are frozen.
- [ ] IF-0-INCREMENTAL-6A -- Boundary cache keys use `boundary:v1:<sha256>` where the hash input is canonical JSON with exactly `path`, `content_hash`, `language`, `grammar_version`, `tool_version`, `schema_version`, `resolution_mode`, `fail_fast`, and `include_retrieval_metadata`; `created_at`, `canonical`, `include_timings`, `incremental`, `cache_dir`, and `force_rebuild` are excluded.
- [ ] IF-0-INCREMENTAL-6B -- `extract_boundary_ir(path, language=None, *, canonical=True, created_at=None, resolution_mode="strict", fail_fast=False, include_timings=False, incremental=False, cache_dir=None, force_rebuild=False)` is the public additive API; `incremental=False` keeps the Phase 4 execution path.
- [ ] IF-0-INCREMENTAL-6C -- `incremental=True` uses a persistent Boundary IR cache under `cache_dir` when provided, otherwise under the user cache namespace for this repository root, and never writes cache data into canonical Boundary IR output.
- [ ] IF-0-INCREMENTAL-6D -- Warm-run invalidation recomputes added files, deleted files, cache-key mismatches, malformed cache records, and impacted neighbors; `force_rebuild=True` bypasses cache reads and refreshes all records.
- [ ] IF-0-INCREMENTAL-6E -- Impacted neighbors are the deterministic union of changed files, previous and current relationship endpoints for those files, and reverse import/dependency/call references whose module or symbol candidates mention changed files.
- [ ] IF-0-INCREMENTAL-6F -- For the same repository snapshot and options with `include_timings=False`, cold incremental output and warm incremental output serialize to identical `dumps_boundary_ir()` bytes.
- [ ] IF-0-INCREMENTAL-6G -- Focused fixture or benchmark coverage demonstrates warm runs reprocess fewer files and report a controlled cold-vs-warm speedup without relying on flaky wall-clock-only assertions.

## Lane Index & Dependencies

- SL-0 -- Incremental constants and contract tests; Depends on: (none); Blocks: SL-1, SL-2, SL-3, SL-4, SL-5, SL-6; Parallel-safe: no
- SL-1 -- Reusable symbol fact extraction; Depends on: SL-0; Blocks: SL-2, SL-3, SL-4, SL-5, SL-6; Parallel-safe: no
- SL-2 -- Boundary cache records; Depends on: SL-0, SL-1; Blocks: SL-3, SL-4, SL-5, SL-6; Parallel-safe: yes
- SL-3 -- Impacted-neighbor analysis; Depends on: SL-0, SL-1, SL-2; Blocks: SL-4, SL-5, SL-6; Parallel-safe: yes
- SL-4 -- Boundary extraction incremental runtime; Depends on: SL-0, SL-1, SL-2, SL-3; Blocks: SL-5, SL-6; Parallel-safe: no
- SL-5 -- CLI and speedup smoke coverage; Depends on: SL-0, SL-2, SL-3, SL-4; Blocks: SL-6; Parallel-safe: yes
- SL-6 -- Documentation and contract synthesis; Depends on: SL-0, SL-1, SL-2, SL-3, SL-4, SL-5; Blocks: (none); Parallel-safe: no

## Lanes

### SL-0 -- Incremental Constants And Contract Tests

- **Scope**: Freeze the cache-key field names and public incremental API expectations before cache and runtime work depends on them.
- **Owned files**: `chunker/boundary/types.py`, `tests/test_boundary_ir_incremental_contract.py`
- **Interfaces provided**: `BOUNDARY_CACHE_VERSION`, `BOUNDARY_CACHE_KEY_PREFIX`, `BOUNDARY_CACHE_KEY_FIELDS`, `BOUNDARY_CACHE_EXCLUDED_OPTION_FIELDS`
- **Interfaces consumed**: Phase 4 `BOUNDARY_IR_SCHEMA_VERSION`, `ResolutionMode`, existing `extract_boundary_ir()` import surface
- **Parallel-safe**: no
- **Tasks**:
  - test: add contract tests asserting cache version/prefix values and exact cache-key field ordering.
  - test: assert `include_timings`, `created_at`, `canonical`, `cache_dir`, `incremental`, and `force_rebuild` are excluded from cache-key input.
  - impl: add constants to `chunker/boundary/types.py` without changing existing schema, metric, timing, diagnostic, or file-status constants.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_incremental_contract.py -q`

### SL-1 -- Reusable Symbol Fact Extraction

- **Scope**: Refactor symbol graph extraction so cold and incremental Boundary IR assembly can reuse per-file symbol facts without changing legacy graph output.
- **Owned files**: `chunker/symbol_graph.py`, `tests/test_symbol_graph_incremental_facts.py`
- **Interfaces provided**: internal per-file symbol fact shape, deterministic `assemble_symbol_graph(...)` behavior, unchanged `extract_symbol_graph(...)` public output
- **Interfaces consumed**: constants from SL-0; existing `collect_source_files()`, `_detect_language()`, `_module_name()`, `_display_file()`, `_reference_candidates()`, `chunk_file()`, `ResolutionMode`
- **Parallel-safe**: no
- **Tasks**:
  - test: add tests proving per-file symbol facts include display file, module, language, symbol lookup entries, import strings, dependency strings, call references, and extraction errors.
  - test: assert assembling symbol facts from all files produces the same `symbols`, `relationships`, `metadata`, `symbol_lookup`, and `errors` shape as `extract_symbol_graph()` for representative Python fixtures.
  - test: preserve strict/permissive relationship resolution behavior and sorted candidate IDs.
  - impl: split current `extract_symbol_graph()` internals into a per-file fact extractor and graph assembler while keeping `extract_symbol_graph()` as the compatibility wrapper.
  - impl: keep legacy default `resolution_mode="permissive"` and `fail_fast=False`; do not introduce Boundary IR cache concerns into `symbol_graph.py`.
  - verify: `uv run --with toml --all-extras pytest tests/test_symbol_graph_incremental_facts.py tests/test_symbol_graph_resolution.py tests/test_symbol_graph.py -q`

### SL-2 -- Boundary Cache Records

- **Scope**: Implement deterministic persisted Boundary IR cache records and index loading/saving.
- **Owned files**: `chunker/boundary/cache.py`, `tests/test_boundary_ir_incremental_cache.py`
- **Interfaces provided**: `build_boundary_cache_key(...)`, `BoundaryCacheRecord`, `BoundaryCacheIndex`, cache index load/save helpers, malformed-record invalidation behavior
- **Interfaces consumed**: cache constants from SL-0; per-file symbol facts from SL-1; `BOUNDARY_IR_SCHEMA_VERSION`; `get_language_info(language).version`; `TOOL_VERSION` or equivalent package version
- **Parallel-safe**: yes
- **Tasks**:
  - test: add unit tests proving cache-key hashes are stable across dictionary ordering and change when any included key field changes.
  - test: prove excluded fields (`created_at`, `canonical`, `include_timings`, `incremental`, `cache_dir`, `force_rebuild`) do not change the cache key.
  - test: prove cache records round-trip as UTF-8 JSON with sorted keys, relative paths, content hash, key payload, file record, node records, symbol facts, diagnostics, and dependency summaries.
  - test: prove missing, unreadable, schema-version-mismatched, or malformed records are treated as cache misses without crashing default extraction.
  - impl: store cache metadata as JSON, not pickle, so boundary cache artifacts are inspectable and cross-platform.
  - impl: write cache files atomically through a temporary file plus replace to avoid partial records on interrupted writes.
  - impl: keep absolute cache storage paths out of cache-key payloads and canonical Boundary IR.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_incremental_cache.py -q`

### SL-3 -- Impacted-Neighbor Analysis

- **Scope**: Compute deterministic file recomputation sets from cache index state and relationship-sensitive references.
- **Owned files**: `chunker/boundary/impact.py`, `tests/test_boundary_ir_incremental_impact.py`
- **Interfaces provided**: `detect_changed_paths(...)`, `compute_impacted_paths(...)`, deterministic impacted-path ordering, deletion invalidation contract
- **Interfaces consumed**: cache records and index from SL-2; per-file symbol fact summaries from SL-1; source file list from `collect_source_files()`
- **Parallel-safe**: yes
- **Tasks**:
  - test: add cases for no-change warm runs returning an empty recompute set.
  - test: add cases for added, deleted, and content-changed files returning those paths plus deterministic neighbor paths.
  - test: prove reverse import, dependency, and call references pull in impacted neighbors when a changed file exports or removes symbols used elsewhere.
  - test: prove unrelated files stay reusable when their cache key is valid and no previous/current relationship endpoint touches a changed path.
  - impl: compute with relative path strings normalized to POSIX separators for stable cache records on Windows and POSIX.
  - impl: sort all returned path lists lexicographically before runtime consumption.
  - impl: keep impact analysis independent from CLI and canonical JSON serialization.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_incremental_impact.py -q`

### SL-4 -- Boundary Extraction Incremental Runtime

- **Scope**: Thread the cache and impact contracts through `extract_boundary_ir()` while preserving default output and cold/warm determinism.
- **Owned files**: `chunker/boundary/adapter.py`, `tests/test_boundary_ir_incremental_runtime.py`, `tests/test_boundary_ir_determinism.py`
- **Interfaces provided**: `extract_boundary_ir(..., incremental=False, cache_dir=None, force_rebuild=False)`, cold incremental cache population, warm incremental reuse, byte-identical cold/warm output
- **Interfaces consumed**: constants from SL-0; symbol facts from SL-1; cache index/records from SL-2; impacted paths from SL-3; existing `canonicalize_boundary_ir()`, `_node_record()`, `_edge_record()`, `_diagnostic()`, `_timings()`
- **Parallel-safe**: no
- **Tasks**:
  - test: add runtime tests proving `incremental=False` keeps default canonical output and `run.options` unchanged.
  - test: assert `extract_boundary_ir` exposes keyword-only `incremental`, `cache_dir`, and `force_rebuild` parameters after existing Phase 4 options, with defaults `False`, `None`, and `False`.
  - test: add a cold incremental run that populates cache records, then a warm run on the same snapshot that reuses records and produces identical `dumps_boundary_ir()` bytes with `include_timings=False`.
  - test: modify one fixture file and prove only the changed file plus impacted neighbors are recomputed while unrelated cached records are reused.
  - test: prove `force_rebuild=True` ignores valid cache records and refreshes the cache.
  - test: prove parser or metadata failures still honor Phase 4 default-continuation and `fail_fast=True` behavior when incremental mode is enabled.
  - impl: keep cache diagnostics out of canonical Boundary IR unless they correspond to actual extraction failures already represented by Phase 4 diagnostics.
  - impl: assemble the final document from cached and recomputed file records, node records, symbol facts, relationships, diagnostics, metrics, and run metadata, then canonicalize through the existing serializer.
  - impl: invalidate stale records for deleted files and avoid leaving deleted nodes or edges in warm output.
  - impl: require `include_timings=False` for cold/warm byte-identity assertions; if timings are requested, preserve Phase 4 opt-in timing semantics.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_incremental_runtime.py tests/test_boundary_ir_determinism.py tests/test_boundary_ir_adapter.py tests/test_boundary_ir_fail_fast.py -q`

### SL-5 -- CLI And Speedup Smoke Coverage

- **Scope**: Expose incremental Boundary IR generation through the CLI and add non-flaky speedup coverage.
- **Owned files**: `cli/main.py`, `tests/test_boundary_ir_cli_incremental.py`, `tests/test_boundary_ir_incremental_benchmark.py`, `scripts/run_ci_smoke.py`
- **Interfaces provided**: `boundary --incremental`, `boundary --cache-dir`, `boundary --force-rebuild`, controlled cold-vs-warm speedup test, CI smoke inclusion
- **Interfaces consumed**: runtime API from SL-4; cache-dir semantics from SL-2; impacted-path semantics from SL-3; existing `boundary` CLI output and summary rules
- **Parallel-safe**: yes
- **Tasks**:
  - test: add CLI tests proving incremental flags pass through and JSON stdout remains parseable and byte-identical between cold and warm runs for the same snapshot.
  - test: add output-file CLI coverage proving cache files are written under `--cache-dir` and `--quiet` still suppresses console summaries.
  - test: add a controlled benchmark/smoke test using fixture repos and monkeypatched extraction delay or counters so warm runs demonstrably reprocess fewer files and report a speedup without relying only on ambient wall-clock timing.
  - impl: add Typer options `--incremental`, `--cache-dir`, and `--force-rebuild` to the existing `boundary` command.
  - impl: keep cache stats out of stdout JSON and out of default summary text unless a focused test defines a stable console-only line.
  - impl: add the narrowest incremental benchmark/smoke test file to `CI_SMOKE_TESTS` only after it is deterministic and fast.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_cli_incremental.py tests/test_boundary_ir_incremental_benchmark.py tests/test_boundary_ir_cli.py tests/test_boundary_ir_cli_observability.py -q`
  - verify: `uv run --with toml --all-extras python scripts/run_ci_smoke.py`

### SL-6 -- Documentation And Contract Synthesis

- **Scope**: Document the finalized incremental cache and recomputation contract after all producer lanes settle.
- **Owned files**: `docs/interface-boundary-spec.md`, `docs/interface-boundary-roadmap.md`, `docs/agent-interface-readiness.md`, `docs/cli-reference.md`, `docs/performance-guide.md`
- **Interfaces provided**: documented IF-0-INCREMENTAL-6 cache-key payload, invalidation rules, impacted-neighbor rules, API/CLI flags, and cold/warm determinism guarantee
- **Interfaces consumed**: constants from SL-0; symbol fact contract from SL-1; cache record behavior from SL-2; impact semantics from SL-3; runtime behavior from SL-4; CLI and benchmark findings from SL-5
- **Parallel-safe**: no
- **Tasks**:
  - test: review executable coverage from SL-0 through SL-5 and add no docs-only tests unless a documented incremental rule lacks a focused assertion.
  - impl: update `docs/interface-boundary-spec.md` with an incremental section that explicitly states cache/runtime stats are not part of canonical Boundary IR output.
  - impl: update roadmap/readiness docs to mark cache key strategy and incremental recomputation as implemented or in progress according to the existing status style.
  - impl: update CLI and performance docs with `--incremental`, `--cache-dir`, `--force-rebuild`, warm-run reuse expectations, and cache invalidation notes.
  - impl: do not broaden docs into distributed cache services, daemon/watch mode, semantic enrichment, ownership policy, or non-deterministic timing requirements.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_incremental_contract.py tests/test_symbol_graph_incremental_facts.py tests/test_boundary_ir_incremental_cache.py tests/test_boundary_ir_incremental_impact.py tests/test_boundary_ir_incremental_runtime.py tests/test_boundary_ir_cli_incremental.py tests/test_boundary_ir_incremental_benchmark.py -q`
  - verify: `uv run --with toml --all-extras mkdocs build --strict`

## Verification

Lane-specific verification is listed in each lane. After all lanes are integrated, run:

```bash
uv run --with toml --all-extras pytest tests/test_boundary_ir_incremental_contract.py tests/test_symbol_graph_incremental_facts.py tests/test_boundary_ir_incremental_cache.py tests/test_boundary_ir_incremental_impact.py tests/test_boundary_ir_incremental_runtime.py tests/test_boundary_ir_cli_incremental.py tests/test_boundary_ir_incremental_benchmark.py tests/test_boundary_ir_determinism.py tests/test_boundary_ir_adapter.py tests/test_boundary_ir_resolution_modes.py tests/test_boundary_ir_observability_metrics.py tests/test_boundary_ir_fail_fast.py tests/test_symbol_graph_resolution.py -q
uv run --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
uv run --all-extras black --check chunker/ cli/ tests/ scripts/
uv run --with toml --all-extras python scripts/run_ci_smoke.py
```

Because this phase touches cache paths, temp files, extraction, fallback/error behavior, and export formatting, run the standing Windows preflight before pushing:

```bash
ssh leno 'powershell -NoProfile -Command "cd $HOME\\code\\treesitter-chunker; git fetch origin; git checkout main; git pull --ff-only; uv run --with toml --all-extras python scripts/run_windows_preflight.py"'
```

## Acceptance Criteria

- [ ] Boundary cache records are keyed by file path, file content hash, language, grammar version, tool version, Boundary IR schema version, resolution mode, `fail_fast`, and `include_retrieval_metadata`.
- [ ] `created_at`, `canonical`, `include_timings`, `incremental`, `cache_dir`, and `force_rebuild` do not affect cache keys and do not enter canonical Boundary IR output.
- [ ] `extract_boundary_ir(..., incremental=True, cache_dir=...)` populates a persistent cache on cold runs and reuses valid records on warm runs.
- [ ] Warm incremental output is byte-identical to cold incremental output for the same repository snapshot when `include_timings=False`.
- [ ] Changed files, deleted files, malformed cache records, and cache-key mismatches are invalidated deterministically.
- [ ] Relationship-sensitive impacted neighbors are recomputed for imports, dependencies, and calls, while unrelated valid records are reused.
- [ ] `force_rebuild=True` bypasses cache reads and refreshes all records.
- [ ] Existing default non-incremental Boundary IR output, golden snapshots, strict/permissive resolution behavior, diagnostics, and `fail_fast` semantics remain compatible.
- [ ] The `boundary` CLI exposes `--incremental`, `--cache-dir`, and `--force-rebuild` without polluting stdout JSON.
- [ ] Fixture or benchmark coverage demonstrates fewer recomputed files and a controlled warm-run speedup.
- [ ] Documentation covers cache-key format, invalidation, impacted neighbors, API/CLI usage, and the canonical-output determinism guarantee.
- [ ] Phase 5 does not add a distributed cache service, watch mode, daemonized indexing, semantic enrichment, ownership policy, or relaxed canonical serialization.
