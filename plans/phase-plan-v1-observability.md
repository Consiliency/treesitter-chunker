# OBSERVABILITY: Diagnostics And Run Observability

## Context

Roadmap source: `specs/phase-plans-v1.md`, Phase 4. The roadmap is currently staged as a new file (`A  specs/phase-plans-v1.md`), so it is not an untracked `git clean -fd` risk.

Phase 1 through Phase 3 artifacts are present in this working tree. `chunker.boundary.extract_boundary_ir()` emits canonical dictionaries from `chunk_file(..., extract_metadata=True, include_retrieval_metadata=True)` and `extract_symbol_graph()`, `chunker.boundary.types.METRIC_KEYS` defines the current deterministic counter set, and conformance fixtures/goldens now cover Python, JavaScript, TypeScript, and Go. Current observability is partial: Boundary IR has basic counters, graph errors are flattened into diagnostics, per-file parser failures continue by default, and the CLI prints only a minimal output-file summary. There is no frozen stage timing contract, no deterministic failure buckets, no public `fail_fast` option, and no focused tests for canonical diagnostic stability.

The existing Boundary IR spec explicitly forbids volatile timing values in byte-identical canonical output unless they are omitted, set to `null`, or moved to a non-canonical report. This phase must therefore freeze timings as stable run metadata keys while keeping default canonical output deterministic. Actual wall-clock timing values are opt-in observability data and must not silently enter the default golden path.

## Interface Freeze Gates

- [ ] IF-0-OBSERVABILITY-5 -- Structured metrics, diagnostics, parse failure handling, and `fail_fast` behavior are frozen for Boundary IR extraction and CLI use.
- [ ] IF-0-OBSERVABILITY-5A -- `extract_boundary_ir(path, language=None, *, canonical=True, created_at=None, resolution_mode="strict", fail_fast=False, include_timings=False)` is the public Boundary IR API contract; `extract_symbol_graph(..., fail_fast=False)` is additive and preserves legacy default behavior.
- [ ] IF-0-OBSERVABILITY-5B -- `run.timings` exists with exactly `parse_ms`, `metadata_normalization_ms`, `graph_assembly_ms`, `resolution_ms`, `serialization_ms`, and `total_ms`; values are `null` by default and nonnegative millisecond numbers only when `include_timings=True`.
- [ ] IF-0-OBSERVABILITY-5C -- `run.options` records deterministic observability-affecting options: `include_retrieval_metadata`, `language`, `resolution_mode`, `fail_fast`, and `include_timings`.
- [ ] IF-0-OBSERVABILITY-5D -- `metrics` keeps the Phase 3 counters and additively includes `files_processed`, `files_failed`, `parse_failures`, `metadata_failures`, `graph_failures`, `serialization_failures`, and `failure_buckets`; `failure_buckets` is a lexicographically sorted code-to-count mapping.
- [ ] IF-0-OBSERVABILITY-5E -- Diagnostic records keep the frozen keys `id`, `severity`, `code`, `message`, `path`, `location`, `stage`, and `details`; diagnostic IDs are deterministic hashes of `stage`, `code`, `path`, `location`, `message`, and canonicalized `details`, not encounter-order indexes.
- [ ] IF-0-OBSERVABILITY-5F -- Default extraction continues after parser or metadata extraction failures, records file status `error`, attaches diagnostic IDs to the failed file record, and emits any successful nodes/edges from other files.
- [ ] IF-0-OBSERVABILITY-5G -- `fail_fast=True` raises on the first parser, metadata extraction, graph extraction, or serialization failure and does not return partial Boundary IR.
- [ ] IF-0-OBSERVABILITY-5H -- The `boundary` CLI exposes `--fail-fast`, `--include-timings`, and `--summary`; JSON written to stdout remains unpolluted by summaries, and summaries are emitted only through the console path when requested or when writing to `--output` without `--quiet`.

## Lane Index & Dependencies

- SL-0 -- Observability constants and contract tests; Depends on: (none); Blocks: SL-1, SL-2, SL-3, SL-4, SL-5; Parallel-safe: no
- SL-1 -- Boundary extraction observability runtime; Depends on: SL-0; Blocks: SL-2, SL-3, SL-4, SL-5; Parallel-safe: no
- SL-2 -- Boundary CLI run summaries; Depends on: SL-0, SL-1; Blocks: SL-3, SL-5; Parallel-safe: yes
- SL-3 -- Canonical conformance and golden stabilization; Depends on: SL-0, SL-1, SL-2; Blocks: SL-5; Parallel-safe: no
- SL-4 -- Recovery and parallel error anchors; Depends on: SL-0, SL-1; Blocks: SL-5; Parallel-safe: yes
- SL-5 -- Documentation and contract synthesis; Depends on: SL-0, SL-1, SL-2, SL-3, SL-4; Blocks: (none); Parallel-safe: no

## Lanes

### SL-0 -- Observability Constants And Contract Tests

- **Scope**: Freeze the observability field names, allowed values, and public API shape before runtime work depends on them.
- **Owned files**: `chunker/boundary/types.py`, `chunker/boundary/__init__.py`, `tests/test_boundary_ir_observability_contract.py`
- **Interfaces provided**: `TIMING_KEYS`, expanded `METRIC_KEYS`, `DIAGNOSTIC_STAGES`, `DIAGNOSTIC_SEVERITIES`, `FILE_STATUSES`, public `extract_boundary_ir()` signature expectations
- **Interfaces consumed**: Phase 3 `TOP_LEVEL_KEYS`, `RESOLUTION_MODES`, `RESOLUTION_STATUSES`, current Boundary IR import surface
- **Parallel-safe**: no
- **Tasks**:
  - test: add contract tests asserting exact timing keys, additive metric keys, diagnostic stages `discovery`, `parse`, `metadata`, `graph`, `resolution`, and `serialization`, severities `info`, `warning`, and `error`, and file statuses `parsed`, `skipped`, and `error`.
  - test: assert `extract_boundary_ir` accepts `fail_fast` and `include_timings` keyword-only parameters with defaults `False`.
  - impl: add constants to `chunker/boundary/types.py` without changing existing schema version or removing Phase 3 keys.
  - impl: update `chunker/boundary/__init__.py` only if new constants need to be exported for tests or downstream consumers.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_observability_contract.py -q`

### SL-1 -- Boundary Extraction Observability Runtime

- **Scope**: Implement structured stage timings, deterministic counters, diagnostics, default continuation, and `fail_fast` behavior in the Boundary IR extraction path.
- **Owned files**: `chunker/boundary/adapter.py`, `chunker/symbol_graph.py`, `tests/test_boundary_ir_observability_metrics.py`, `tests/test_boundary_ir_diagnostics.py`, `tests/test_boundary_ir_fail_fast.py`
- **Interfaces provided**: `extract_boundary_ir(..., fail_fast=False, include_timings=False)`, `extract_symbol_graph(..., fail_fast=False)`, deterministic diagnostics, expanded metrics, `run.timings`, default-continue failure handling
- **Interfaces consumed**: constants from SL-0; existing `chunk_file()`, `collect_source_files()`, `extract_symbol_graph()`, `canonicalize_boundary_ir()`, `ResolutionMode`
- **Parallel-safe**: no
- **Tasks**:
  - test: add metrics tests proving default `run.timings` contains all timing keys with `None` values, `include_timings=True` emits nonnegative numeric timing values, and existing counters still match emitted files/nodes/edges/diagnostics.
  - test: add counter tests for `files_processed`, `files_failed`, `parse_failures`, `metadata_failures`, `graph_failures`, `serialization_failures`, and deterministic `failure_buckets`.
  - test: add diagnostics tests using monkeypatched parser/chunk failures so one source file fails while another file still emits nodes; assert file status `error`, file diagnostic IDs, diagnostic stage/code/path/details, and canonical diagnostic ordering are stable across two runs.
  - test: add `fail_fast=True` tests proving parser, metadata, graph, and serialization failures raise without returning partial Boundary IR, while default extraction records diagnostics and continues where possible.
  - impl: replace encounter-index diagnostic IDs with deterministic hashes over canonical diagnostic content.
  - impl: keep default `include_timings=False` deterministic by setting timing values to `None`; when `include_timings=True`, measure stage durations with `time.perf_counter()` and round consistently.
  - impl: add timing spans around source discovery, per-file parsing/chunk extraction, node metadata normalization, symbol graph assembly, Boundary IR edge resolution/assembly, and final canonicalization/serialization preparation.
  - impl: add `fail_fast` to `extract_symbol_graph()` as a default-off compatibility parameter so graph extraction can either preserve existing error accumulation or raise on first extraction failure.
  - impl: preserve current strict/permissive resolution behavior and existing symbol graph CLI defaults.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_observability_metrics.py tests/test_boundary_ir_diagnostics.py tests/test_boundary_ir_fail_fast.py -q`

### SL-2 -- Boundary CLI Run Summaries

- **Scope**: Expose observability controls and concise deterministic summaries through the `boundary` CLI without corrupting JSON output.
- **Owned files**: `cli/main.py`, `tests/test_boundary_ir_cli_observability.py`
- **Interfaces provided**: `boundary --fail-fast`, `boundary --include-timings`, `boundary --summary`, summary fields for files processed/skipped/failed, parse failures, ambiguous/unresolved edges, nodes, edges, diagnostics, and failure buckets
- **Interfaces consumed**: `extract_boundary_ir(..., fail_fast=..., include_timings=...)` and expanded metrics/run metadata from SL-1
- **Parallel-safe**: yes
- **Tasks**:
  - test: add CLI tests proving `--fail-fast` passes through and exits nonzero on a forced extraction failure.
  - test: add CLI tests proving `--include-timings` emits numeric `run.timings` values in JSON and default output emits `null` timing values.
  - test: add CLI tests proving stdout JSON remains parseable when no `--output` is used, and summary text appears only when `--summary` is requested or when `--output` is used without `--quiet`.
  - impl: add Typer options for `--fail-fast`, `--include-timings`, and `--summary`.
  - impl: format summary labels in a fixed order from metrics, never from unsorted diagnostic or failure-bucket iteration.
  - impl: keep the existing `--quiet` behavior as the summary suppressor for output-file mode.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_cli_observability.py tests/test_boundary_ir_cli.py -q`

### SL-3 -- Canonical Conformance And Golden Stabilization

- **Scope**: Update the conformance harness and golden snapshots so observability fields are stable in canonical output.
- **Owned files**: `tests/boundary_ir_conformance.py`, `tests/test_boundary_ir_required_fields.py`, `tests/test_boundary_ir_determinism.py`, `tests/test_boundary_ir_golden_snapshots.py`, `tests/fixtures/boundary_ir/golden/**`
- **Interfaces provided**: updated required-field validation for `metrics`, `run.options`, and `run.timings`; canonical golden snapshots with default `null` timing values; determinism coverage for diagnostics
- **Interfaces consumed**: constants from SL-0; runtime behavior from SL-1; CLI summary behavior from SL-2 when deciding smoke coverage impact
- **Parallel-safe**: no
- **Tasks**:
  - test: update `assert_required_fields()` to validate expanded `METRIC_KEYS`, `run.timings`, and expanded `run.options`.
  - test: add or extend determinism coverage so diagnostic-bearing fixture or monkeypatched extraction output is byte-identical across two default canonical runs.
  - impl: update golden snapshots only after SL-1 output is settled; default snapshots must keep all timing values `null` and must not normalize diagnostics, metrics, `run.options`, or `run.timings`.
  - impl: keep `tests/test_boundary_ir_golden_snapshots.py` normalization limited to `run.tool_version`.
  - impl: leave `scripts/run_ci_smoke.py` unchanged unless the existing golden snapshot smoke gate stops covering the expanded required fields.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_required_fields.py tests/test_boundary_ir_determinism.py tests/test_boundary_ir_golden_snapshots.py tests/test_boundary_ir_observability_metrics.py tests/test_boundary_ir_diagnostics.py -q`

### SL-4 -- Recovery And Parallel Error Anchors

- **Scope**: Tie Boundary IR diagnostics and `fail_fast` behavior back to the repository's existing recovery/error-handling coverage.
- **Owned files**: `tests/test_recovery.py`, `tests/test_parallel_error_handling.py`
- **Interfaces provided**: regression anchors that Boundary IR preserves partial results by default and exposes strict failure behavior when requested
- **Interfaces consumed**: failure semantics and diagnostics from SL-1
- **Parallel-safe**: yes
- **Tasks**:
  - test: add focused recovery assertions, or update existing recovery tests, so Boundary IR default extraction preserves successful file results when one file's chunk extraction fails.
  - test: add focused parallel/error assertions only if the existing parallel error tests need a Boundary IR-specific check for failure summaries or diagnostic propagation.
  - impl: avoid adding production code in this lane; if a production change is required, move that requirement back to SL-1 to preserve single-writer ownership.
  - verify: `uv run --with toml --all-extras pytest tests/test_recovery.py tests/test_parallel_error_handling.py -q`

### SL-5 -- Documentation And Contract Synthesis

- **Scope**: Document the finalized observability contract after all producer lanes settle.
- **Owned files**: `docs/interface-boundary-spec.md`, `docs/interface-boundary-roadmap.md`, `docs/agent-interface-readiness.md`, `docs/cli-reference.md`, `docs/user-guide.md`
- **Interfaces provided**: documented IF-0-OBSERVABILITY-5 timing, metrics, diagnostics, default-continuation, `fail_fast`, and CLI summary contracts
- **Interfaces consumed**: constants from SL-0; runtime behavior and failure semantics from SL-1; CLI flags and summary output from SL-2; conformance/golden behavior from SL-3; recovery findings from SL-4
- **Parallel-safe**: no
- **Tasks**:
  - test: review docs against executable tests and add no docs-only tests unless a documented observability rule lacks a focused test.
  - impl: update `docs/interface-boundary-spec.md` with `run.timings`, expanded `metrics`, diagnostic ID determinism, failure bucket rules, and the rule that default canonical output keeps timing values `null`.
  - impl: update CLI docs for `--fail-fast`, `--include-timings`, `--summary`, and `--quiet` summary suppression.
  - impl: update roadmap/readiness docs only where existing status conventions call for marking IF-0-OBSERVABILITY-5 as implemented or in progress.
  - impl: do not broaden docs into incremental recomputation, semantic enrichment, external telemetry, ownership policy, or performance tuning.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_observability_contract.py tests/test_boundary_ir_observability_metrics.py tests/test_boundary_ir_diagnostics.py tests/test_boundary_ir_fail_fast.py tests/test_boundary_ir_cli_observability.py tests/test_boundary_ir_required_fields.py tests/test_boundary_ir_determinism.py tests/test_boundary_ir_golden_snapshots.py -q`
  - verify: `uv run --with toml --all-extras mkdocs build --strict`

## Verification

Lane-specific verification is listed in each lane. After all lanes are integrated, run:

```bash
uv run --with toml --all-extras pytest tests/test_boundary_ir_observability_contract.py tests/test_boundary_ir_observability_metrics.py tests/test_boundary_ir_diagnostics.py tests/test_boundary_ir_fail_fast.py tests/test_boundary_ir_cli_observability.py tests/test_boundary_ir_required_fields.py tests/test_boundary_ir_determinism.py tests/test_boundary_ir_golden_snapshots.py tests/test_boundary_ir_adapter.py tests/test_boundary_ir_resolution_modes.py tests/test_symbol_graph_resolution.py -q
uv run --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
uv run --all-extras black --check chunker/ cli/ tests/ scripts/
uv run --with toml --all-extras python scripts/run_ci_smoke.py
```

Because this phase touches paths, parser failure handling, export formatting, and canonical JSON shape, run the standing Windows preflight before pushing:

```bash
ssh leno 'powershell -NoProfile -Command "cd $HOME\\code\\treesitter-chunker; git fetch origin; git checkout main; git pull --ff-only; uv run --with toml --all-extras python scripts/run_windows_preflight.py"'
```

## Acceptance Criteria

- [ ] Boundary IR `run.timings` includes `parse_ms`, `metadata_normalization_ms`, `graph_assembly_ms`, `resolution_ms`, `serialization_ms`, and `total_ms`.
- [ ] Default canonical output remains byte-identical across double runs because timing values are `null` unless `include_timings=True`.
- [ ] `include_timings=True` emits nonnegative numeric timing values and records `run.options.include_timings`.
- [ ] Run metrics include files processed, skipped files, failed files, parse failures, ambiguous edges, unresolved edges, emitted nodes, emitted edges, diagnostics, and deterministic failure buckets.
- [ ] Parse and extraction failures continue by default, mark affected file records as `error`, attach structured diagnostics, and preserve successful output from unaffected files.
- [ ] `fail_fast=True` stops on the first parser, metadata extraction, graph extraction, or serialization failure and raises instead of returning partial Boundary IR.
- [ ] Diagnostic records have deterministic IDs and stable canonical ordering.
- [ ] The `boundary` CLI exposes `--fail-fast`, `--include-timings`, and `--summary` without polluting stdout JSON.
- [ ] Focused observability tests cover metrics, diagnostics, `fail_fast`, CLI summary behavior, and canonical diagnostic stability.
- [ ] Golden snapshots and required-field helpers reflect the expanded observability contract.
- [ ] Existing Boundary IR adapter, resolution-mode, CLI, symbol graph, and conformance tests continue to pass.
- [ ] Phase 4 does not add external telemetry service integration, performance tuning beyond measurement reliability, incremental recomputation, semantic enrichment, or ownership policy enforcement.
