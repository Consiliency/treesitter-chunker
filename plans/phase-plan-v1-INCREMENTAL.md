---
phase_loop_plan_version: 1
phase: INCREMENTAL
roadmap: specs/phase-plans-v1.md
roadmap_sha256: 8e02fa7e008f0a7df7dd7b28c36c2c2eb2ab79b5ebdc52cb8e3fd611efee277c
---

# INCREMENTAL: Incremental Boundary Recompute

## Context

Roadmap source: `specs/phase-plans-v1.md`, Phase 5 (`INCREMENTAL`). Canonical
`.phase-loop/state.json` still records `OBSERVABILITY` as `planned` and
`INCREMENTAL` as `unplanned`, so this artifact is the requested write-through
plan output, not authorization to skip the Phase 4 dependency chain. The repo
is clean on `main` at `8d0e18a5`, and the roadmap hash matches the required
`8e02fa7e008f0a7df7dd7b28c36c2c2eb2ab79b5ebdc52cb8e3fd611efee277c`.

This checkout is materially ahead of the original Phase 5 baseline. The live
repo already contains incremental Boundary IR constants in
`chunker/boundary/types.py`, persistent cache records in
`chunker/boundary/cache.py`, impacted-path analysis in
`chunker/boundary/impact.py`, the incremental runtime in
`chunker/boundary/adapter.py`, CLI flags in `cli/main.py`, focused tests in
`tests/test_boundary_ir_incremental_contract.py`,
`tests/test_symbol_graph_incremental_facts.py`,
`tests/test_boundary_ir_incremental_cache.py`,
`tests/test_boundary_ir_incremental_impact.py`,
`tests/test_boundary_ir_incremental_runtime.py`,
`tests/test_boundary_ir_cli_incremental.py`, and
`tests/test_boundary_ir_incremental_benchmark.py`, plus corresponding docs in
`docs/interface-boundary-spec.md`, `docs/interface-boundary-roadmap.md`,
`docs/agent-interface-readiness.md`, `docs/cli-reference.md`, and
`docs/performance-guide.md`.

INCREMENTAL execution should therefore audit and harden the already-landed
implementation instead of rebuilding Phase 5 from scratch. The job is to
reconcile the roadmap contract with the live cache-key surface, invalidation
rules, impacted-neighbor recomputation, cold-versus-warm determinism, CLI
pass-through, and docs/tests while preserving Phase 4 observability behavior
and later additive semantic options. The older lowercase artifact was removed
to avoid case-insensitive filesystem collisions. Phase-loop execution for this
run should use this uppercase
`plans/phase-plan-v1-INCREMENTAL.md` artifact after `OBSERVABILITY` is complete.

## Interface Freeze Gates

- [ ] IF-0-INCREMENTAL-6 - Boundary cache key format, warm-run invalidation
  rules, and impacted-neighbor recomputation contract are frozen.
- [ ] IF-0-INCREMENTAL-6A - `extract_boundary_ir(path, language=None, *,
  canonical=True, created_at=None, resolution_mode="strict", fail_fast=False,
  include_timings=False, incremental=False, cache_dir=None,
  force_rebuild=False, semantic_resolvers=None,
  semantic_min_confidence=0.0)` preserves current additive compatibility;
  `incremental=False` keeps the Phase 4 path, and incremental work may not
  regress semantic option plumbing or syntax-only default output.
- [ ] IF-0-INCREMENTAL-6B - The cache-key constants are frozen to the live
  contract in `chunker/boundary/types.py`:
  `BOUNDARY_CACHE_VERSION == "1"`,
  `BOUNDARY_CACHE_KEY_PREFIX == "boundary:v1:"`,
  `BOUNDARY_CACHE_KEY_FIELDS == ("path", "content_hash", "language",
  "grammar_version", "tool_version", "schema_version", "resolution_mode",
  "fail_fast", "include_retrieval_metadata")`, and
  `BOUNDARY_CACHE_EXCLUDED_OPTION_FIELDS == ("created_at", "canonical",
  "include_timings", "incremental", "cache_dir", "force_rebuild")`.
- [ ] IF-0-INCREMENTAL-6C - `build_boundary_cache_key(...)` hashes only the
  frozen included fields, and cache records/indexes persist as UTF-8 JSON with
  sorted keys, inspectable relative paths, and no absolute cache storage paths
  embedded in canonical Boundary IR output.
- [ ] IF-0-INCREMENTAL-6D - Warm-run invalidation recomputes added files,
  deleted files, cache-key mismatches, malformed cache records, and
  relationship-impacted neighbors; `force_rebuild=True` bypasses valid cache
  reuse and refreshes all records.
- [ ] IF-0-INCREMENTAL-6E - `detect_changed_paths(...)` and
  `compute_impacted_paths(...)` keep deterministic lexicographic ordering and
  define impacted neighbors as the union of changed files, deleted files,
  prior/current relationship endpoints, exported symbols, and module/reference
  tokens needed to repair import, dependency, and call edges.
- [ ] IF-0-INCREMENTAL-6F - For the same repository snapshot and options with
  `include_timings=False`, cold incremental output and warm incremental output
  serialize to identical `dumps_boundary_ir()` bytes and do not add cache stats
  or cache-only metadata to canonical JSON.
- [ ] IF-0-INCREMENTAL-6G - The `boundary` CLI exposes `--incremental`,
  `--cache-dir`, and `--force-rebuild`; stdout JSON stays parseable and stable,
  output-file mode still honors `--quiet`, and deterministic warm-run coverage
  proves fewer files are recomputed without relying on flaky wall-clock-only
  thresholds.

## Lane Index & Dependencies

- SL-0 - Incremental contract audit and additive-surface freeze; Depends on:
  (none); Blocks: SL-1, SL-2, SL-3, SL-4, SL-5; Parallel-safe: no
- SL-1 - Reusable symbol facts and graph-compatibility audit; Depends on:
  SL-0; Blocks: SL-2, SL-3, SL-4, SL-5; Parallel-safe: no
- SL-2 - Boundary cache persistence and invalidation contract; Depends on:
  SL-0, SL-1; Blocks: SL-3, SL-4, SL-5; Parallel-safe: yes
- SL-3 - Impacted-neighbor analysis and incremental runtime determinism;
  Depends on: SL-0, SL-1, SL-2; Blocks: SL-4, SL-5; Parallel-safe: no
- SL-4 - CLI pass-through and deterministic speedup coverage; Depends on:
  SL-0, SL-2, SL-3; Blocks: SL-5; Parallel-safe: yes
- SL-5 - Documentation and roadmap synthesis; Depends on: SL-0, SL-1, SL-2,
  SL-3, SL-4; Blocks: (none); Parallel-safe: no

## Lanes

### SL-0 - Incremental Contract Audit And Additive-Surface Freeze

- **Scope**: Freeze the live Phase 5 constants and public API expectations
  before cache, runtime, CLI, or docs work depends on them.
- **Owned files**: `chunker/boundary/types.py`, `tests/test_boundary_ir_incremental_contract.py`
- **Interfaces provided**: `BOUNDARY_CACHE_VERSION`,
  `BOUNDARY_CACHE_KEY_PREFIX`, `BOUNDARY_CACHE_KEY_FIELDS`,
  `BOUNDARY_CACHE_EXCLUDED_OPTION_FIELDS`,
  `extract_boundary_ir(...)` incremental signature expectations
- **Interfaces consumed**: existing `BOUNDARY_IR_SCHEMA_VERSION`,
  `BOUNDARY_IR_SEMANTIC_SCHEMA_VERSION`, `ResolutionMode`,
  `extract_boundary_ir(...)` public import surface
- **Parallel-safe**: no
- **Tasks**:
  - test: tighten contract tests around the exact cache-key constants and the
    additive keyword-only signature for `incremental`, `cache_dir`, and
    `force_rebuild`.
  - test: prove excluded option fields remain excluded even as later semantic
    support stays additive rather than becoming part of the Phase 5 cache key.
  - impl: update `chunker/boundary/types.py` only where the live constants or
    signature expectations have drifted from the intended roadmap contract.
  - impl: do not widen this lane into runtime logic, observability keys, or
    semantic-schema changes.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_incremental_contract.py -q`

### SL-1 - Reusable Symbol Facts And Graph-Compatibility Audit

- **Scope**: Keep the per-file symbol-fact substrate deterministic and
  compatible so incremental assembly does not fork the legacy symbol-graph
  contract.
- **Owned files**: `chunker/symbol_graph.py`, `tests/test_symbol_graph_incremental_facts.py`
- **Interfaces provided**: per-file symbol-fact extraction, deterministic
  graph assembly, unchanged public `extract_symbol_graph(...)` behavior
- **Interfaces consumed**: SL-0 constant freeze; existing
  `collect_source_files()`, `_detect_language()`, `_module_name()`,
  `_display_file()`, `_reference_candidates()`, `chunk_file()`,
  `ResolutionMode`
- **Parallel-safe**: no
- **Tasks**:
  - test: keep symbol-fact tests explicit about display path, module, language,
    lookup entries, imports, dependencies, calls, and extraction-error capture.
  - test: prove assembling graph state from symbol facts still matches the
    compatibility shape of `extract_symbol_graph()` on representative fixtures.
  - test: preserve strict and permissive relationship-resolution behavior and
    deterministic candidate ordering while incremental reuse is exercised.
  - impl: fix only concrete drift between the live symbol-fact substrate and
    the compatibility wrapper; do not introduce cache storage concerns here.
  - verify: `uv run --with toml --all-extras pytest tests/test_symbol_graph_incremental_facts.py tests/test_symbol_graph_resolution.py tests/test_symbol_graph.py -q`

### SL-2 - Boundary Cache Persistence And Invalidation Contract

- **Scope**: Audit and minimally harden persisted Boundary IR cache records,
  index behavior, and cache-miss recovery.
- **Owned files**: `chunker/boundary/cache.py`, `tests/test_boundary_ir_incremental_cache.py`
- **Interfaces provided**: `build_boundary_cache_key(...)`,
  `BoundaryCacheRecord`, `BoundaryCacheIndex`, cache index load/save helpers,
  malformed-record invalidation behavior
- **Interfaces consumed**: SL-0 cache constants; SL-1 symbol-fact summaries;
  `BOUNDARY_IR_SCHEMA_VERSION`; package version and grammar-version probes used
  by the incremental runtime
- **Parallel-safe**: yes
- **Tasks**:
  - test: keep cache-key tests explicit that reordering payload dictionaries
    does not change the hash, while included fields do.
  - test: prove excluded fields such as `created_at`, `include_timings`,
    `incremental`, `cache_dir`, and `force_rebuild` do not affect cache keys.
  - test: prove cache records and indexes round-trip as UTF-8 JSON and that
    malformed or mismatched data is treated as a miss rather than a crash.
  - impl: fix persistence or invalidation drift only where the focused tests
    expose it; keep cache files human-inspectable and written atomically.
  - impl: preserve relative-path normalization and keep cache storage details
    out of canonical Boundary IR output.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_incremental_cache.py -q`

### SL-3 - Impacted-Neighbor Analysis And Incremental Runtime Determinism

- **Scope**: Reconcile changed-path detection, impacted-neighbor recomputation,
  and cold-versus-warm Boundary IR assembly without regressing Phase 4 failure
  semantics.
- **Owned files**: `chunker/boundary/impact.py`, `chunker/boundary/adapter.py`, `tests/test_boundary_ir_incremental_impact.py`, `tests/test_boundary_ir_incremental_runtime.py`, `tests/test_boundary_ir_determinism.py`
- **Interfaces provided**: `detect_changed_paths(...)`,
  `compute_impacted_paths(...)`,
  `extract_boundary_ir(..., incremental=False, cache_dir=None, force_rebuild=False)`,
  byte-identical cold and warm incremental output
- **Interfaces consumed**: SL-0 cache-key freeze; SL-1 symbol facts; SL-2
  cache/index behavior; existing `canonicalize_boundary_ir()`,
  `_node_record()`, `_edge_record()`, `_diagnostic()`, `_timings()`,
  Phase 4 diagnostics and `fail_fast` behavior
- **Parallel-safe**: no
- **Tasks**:
  - test: keep impact-analysis tests explicit about no-change warm runs,
    added/deleted/changed file handling, reverse-reference neighbors, and
    deterministic lexicographic ordering.
  - test: keep runtime tests explicit that `incremental=False` leaves default
    canonical output and `run.options` unchanged.
  - test: prove cold incremental runs populate cache records, warm runs reuse
    valid records, changed files recompute with impacted neighbors only, and
    `force_rebuild=True` refreshes otherwise-valid records.
  - test: preserve Phase 4 parser and metadata failure behavior under
    incremental mode, including `fail_fast=True` raising immediately.
  - impl: fix only concrete recomputation, invalidation, or determinism drift
    exposed by the focused tests; do not widen this lane into performance
    tuning, daemonization, or semantic enrichment.
  - impl: keep cache diagnostics out of canonical Boundary IR unless they
    correspond to real extraction failures already represented by the Phase 4
    diagnostic contract.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_incremental_impact.py tests/test_boundary_ir_incremental_runtime.py tests/test_boundary_ir_determinism.py tests/test_boundary_ir_fail_fast.py tests/test_boundary_ir_adapter.py -q`

### SL-4 - CLI Pass-Through And Deterministic Speedup Coverage

- **Scope**: Freeze the operator-facing incremental CLI behavior and keep warm
  run speedup proof deterministic and non-flaky.
- **Owned files**: `cli/main.py`, `tests/test_boundary_ir_cli_incremental.py`, `tests/test_boundary_ir_incremental_benchmark.py`, `scripts/run_ci_smoke.py`
- **Interfaces provided**: `boundary --incremental`, `boundary --cache-dir`,
  `boundary --force-rebuild`, stable stdout/stderr behavior, deterministic
  warm-run reprocessing coverage in smoke
- **Interfaces consumed**: SL-2 cache semantics; SL-3 runtime behavior;
  existing `boundary` CLI output and summary rules
- **Parallel-safe**: yes
- **Tasks**:
  - test: keep CLI tests explicit that incremental flags pass through, stdout
    JSON stays parseable, warm JSON remains stable for identical snapshots, and
    output-file mode still honors `--quiet`.
  - test: keep benchmark coverage deterministic by asserting fewer recomputed
    files or equivalent controlled work-count reduction rather than relying only
    on wall-clock timing.
  - impl: fix CLI drift only where the focused tests expose it; keep cache
    stats out of canonical stdout JSON and default summaries unless a test
    freezes a console-only line.
  - impl: keep `scripts/run_ci_smoke.py` changes narrow and only if the settled
    incremental proof needs smoke-lane coverage adjustment.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_cli_incremental.py tests/test_boundary_ir_incremental_benchmark.py tests/test_boundary_ir_cli.py tests/test_boundary_ir_cli_observability.py -q`
  - verify: `uv run --with toml --all-extras python scripts/run_ci_smoke.py`

### SL-5 - Documentation And Roadmap Synthesis

- **Scope**: Update the human-readable incremental contract after the producer
  lanes settle the exact live behavior.
- **Owned files**: `docs/interface-boundary-spec.md`, `docs/interface-boundary-roadmap.md`, `docs/agent-interface-readiness.md`, `docs/cli-reference.md`, `docs/performance-guide.md`
- **Interfaces provided**: docs that match the settled Phase 5 cache-key,
  invalidation, impacted-neighbor, API, CLI, and determinism contract
- **Interfaces consumed**: SL-0 through SL-4 constants, runtime behavior, CLI
  rules, and deterministic warm-run findings
- **Parallel-safe**: no
- **Tasks**:
  - test: review executable coverage from SL-0 through SL-4 and add no docs-only
    assertions unless a documented incremental rule lacks a focused test anchor.
  - impl: update `docs/interface-boundary-spec.md` with the finalized cache-key
    payload, invalidation rules, and the guarantee that cache/runtime stats are
    not part of canonical Boundary IR output.
  - impl: update roadmap/readiness docs only where status prose or Phase 5
    scope wording drifts from the settled implementation and test surface.
  - impl: update CLI and performance docs only where the current `--incremental`,
    `--cache-dir`, `--force-rebuild`, and warm-run reuse behavior is inaccurate
    or incomplete.
  - impl: do not broaden docs into distributed caches, watch mode, daemonized
    indexing, ownership policy, or semantic-enrichment planning.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_incremental_contract.py tests/test_symbol_graph_incremental_facts.py tests/test_boundary_ir_incremental_cache.py tests/test_boundary_ir_incremental_impact.py tests/test_boundary_ir_incremental_runtime.py tests/test_boundary_ir_cli_incremental.py tests/test_boundary_ir_incremental_benchmark.py -q`
  - verify: `uv run --with toml --all-extras mkdocs build --strict`

## Verification

Planning wrote the artifact only; verification was not run. During execution,
run the Phase 5-focused checks first, then the repo-standard local CI loop from
`AGENTS.md`:

```bash
uv run --with toml --all-extras pytest tests/test_boundary_ir_incremental_contract.py tests/test_symbol_graph_incremental_facts.py tests/test_boundary_ir_incremental_cache.py tests/test_boundary_ir_incremental_impact.py tests/test_boundary_ir_incremental_runtime.py tests/test_boundary_ir_cli_incremental.py tests/test_boundary_ir_incremental_benchmark.py tests/test_boundary_ir_determinism.py tests/test_boundary_ir_fail_fast.py tests/test_boundary_ir_adapter.py tests/test_symbol_graph_resolution.py -q
uv run --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
uv run --all-extras black --check chunker/ cli/ tests/ scripts/
uv run --with toml --all-extras python scripts/run_ci_smoke.py
```

Because this phase touches cache paths, temp-file handling, extraction,
invalidation, fallback/error behavior, and output formatting, run the standing
Windows preflight before pushing:

```bash
ssh win 'powershell -NoProfile -Command "cd $HOME\\code\\treesitter-chunker; git fetch origin; git checkout main; git pull --ff-only; uv run --with toml --all-extras python scripts/run_windows_preflight.py"'
```

## Acceptance Criteria

- [ ] The uppercase execution artifact
  `plans/phase-plan-v1-INCREMENTAL.md` is the authoritative Phase 5 plan for
  the current roadmap hash `8e02fa7e008f0a7df7dd7b28c36c2c2eb2ab79b5ebdc52cb8e3fd611efee277c`.
- [ ] Cache-key constants, included fields, and excluded fields match the live
  `chunker/boundary/types.py` contract and remain covered by focused tests.
- [ ] `build_boundary_cache_key(...)`, `BoundaryCacheRecord`, and
  `BoundaryCacheIndex` preserve deterministic JSON persistence and treat
  malformed or mismatched records as cache misses instead of crashes.
- [ ] `detect_changed_paths(...)` and `compute_impacted_paths(...)` deterministically
  identify changed files, deleted files, and relationship-sensitive impacted
  neighbors for imports, dependencies, and calls.
- [ ] `extract_boundary_ir(..., incremental=True, cache_dir=...)` populates and
  reuses persistent cache records without changing default non-incremental
  `run.options`, diagnostics, or canonical JSON structure.
- [ ] Warm incremental output is byte-identical to cold incremental output for
  the same repository snapshot when `include_timings=False`.
- [ ] `force_rebuild=True` bypasses valid cache reuse and refreshes all records.
- [ ] The `boundary` CLI exposes `--incremental`, `--cache-dir`, and
  `--force-rebuild` without polluting stdout JSON or breaking quiet output-file
  mode.
- [ ] Deterministic test or smoke coverage proves warm runs reprocess fewer
  files than cold runs without relying only on ambient wall-clock timing.
- [ ] Docs match the finalized cache-key, invalidation, API, CLI, and
  determinism contract.
- [ ] Phase 5 does not broaden into distributed caches, watch mode, daemonized
  indexing, ownership policy, or semantic-enrichment behavior changes.
