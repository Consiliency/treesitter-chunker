---
phase_loop_plan_version: 1
phase: OBSERVABILITY
roadmap: specs/phase-plans-v1.md
roadmap_sha256: 602ecab108f0f5f143211a29b4945e2fef0bd97e0f467f646b1c78d775d46d7f
---

# OBSERVABILITY: Diagnostics And Run Observability

## Context

Roadmap source: `specs/phase-plans-v1.md`, Phase 4 (`OBSERVABILITY`).
Canonical `.phase-loop/state.json` still records `CONFORMANCE` as the nearest
unfinished dependency and `OBSERVABILITY` as `unplanned`, but this run
explicitly requested the Phase 4 planning artifact. The repo is clean on
`main` at `4e0c2e5f`, and the roadmap hash matches the required
`602ecab108f0f5f143211a29b4945e2fef0bd97e0f467f646b1c78d775d46d7f`.

This checkout is materially ahead of the original Phase 4 baseline. The live
repo already contains observability-related constants and runtime surfaces in
`chunker/boundary/types.py`, `chunker/boundary/adapter.py`,
`chunker/symbol_graph.py`, and `cli/main.py`; focused tests already exist in
`tests/test_boundary_ir_observability_contract.py`,
`tests/test_boundary_ir_observability_metrics.py`,
`tests/test_boundary_ir_diagnostics.py`,
`tests/test_boundary_ir_fail_fast.py`, and
`tests/test_boundary_ir_cli_observability.py`; and docs already describe
timings, summaries, and `fail_fast` behavior.

OBSERVABILITY execution should therefore audit and harden the current
implementation instead of rebuilding Phase 4 from scratch. The primary job is
to reconcile live code, tests, docs, and golden fixtures around deterministic
diagnostics, timing keys, summary behavior, and failure semantics while
preserving later additive surfaces such as incremental cache support and
optional semantic resolvers. The older lowercase artifact
`plans/phase-plan-v1-observability.md` exists as historical planning context
only. Phase-loop execution for this run should follow this uppercase
`plans/phase-plan-v1-OBSERVABILITY.md` artifact once the Phase 3 dependency
chain is satisfied.

## Interface Freeze Gates

- [ ] IF-0-OBSERVABILITY-5 - Structured metrics, diagnostics, parse failure
  handling, and `fail_fast` contract are frozen for Boundary IR extraction and
  CLI use.
- [ ] IF-0-OBSERVABILITY-5A - `extract_boundary_ir(path, language=None, *,
  canonical=True, created_at=None, resolution_mode="strict", fail_fast=False,
  include_timings=False, incremental=False, cache_dir=None,
  force_rebuild=False, semantic_resolvers=None,
  semantic_min_confidence=0.0)` preserves current additive compatibility;
  observability work may not regress incremental or semantic option plumbing.
- [ ] IF-0-OBSERVABILITY-5B - `extract_symbol_graph(path, language=None,
  resolution_mode="permissive", fail_fast=False)` remains the Boundary IR graph
  producer and keeps default-off fail-fast compatibility.
- [ ] IF-0-OBSERVABILITY-5C - `run.timings` exists with exactly `parse_ms`,
  `metadata_normalization_ms`, `graph_assembly_ms`, `resolution_ms`,
  `serialization_ms`, and `total_ms`; values stay `null` by default and are
  nonnegative millisecond numbers only when `include_timings=True`.
- [ ] IF-0-OBSERVABILITY-5D - Base `run.options` keys are exactly
  `include_retrieval_metadata`, `language`, `resolution_mode`, `fail_fast`, and
  `include_timings`; semantic-specific option fields remain additive and appear
  only when semantic resolvers are requested.
- [ ] IF-0-OBSERVABILITY-5E - `metrics` is frozen to the live `METRIC_KEYS`
  contract, including `files_total`, `files_processed`, `files_parsed`,
  `files_skipped`, `files_failed`, `nodes_total`, `edges_total`,
  `diagnostics_total`, `resolved_edges`, `ambiguous_edges`,
  `unresolved_edges`, `parse_failures`, `metadata_failures`, `graph_failures`,
  `serialization_failures`, and deterministic `failure_buckets`.
- [ ] IF-0-OBSERVABILITY-5F - Diagnostic records keep the frozen keys `id`,
  `severity`, `code`, `message`, `path`, `location`, `stage`, and `details`;
  IDs are deterministic hashes over canonical diagnostic content rather than
  encounter-order indexes; any semantic-stage diagnostics remain an additive
  extension rather than an undocumented Phase 4 regression.
- [ ] IF-0-OBSERVABILITY-5G - Default extraction continues after parser,
  metadata, graph, or serialization failures, records failed file status
  `error`, attaches diagnostic IDs to failed file records, and preserves
  successful output from unaffected files.
- [ ] IF-0-OBSERVABILITY-5H - `fail_fast=True` raises on the first parser,
  metadata, graph, or serialization failure and does not return partial
  Boundary IR.
- [ ] IF-0-OBSERVABILITY-5I - The `boundary` CLI exposes `--fail-fast`,
  `--include-timings`, and `--summary`; stdout JSON remains parseable, summary
  output stays on stderr when JSON goes to stdout, and output-file mode prints
  the summary only when `--quiet` is not set.

## Lane Index & Dependencies

- SL-0 - Observability contract audit and additive-extension freeze; Depends
  on: (none); Blocks: SL-1, SL-2, SL-3, SL-4, SL-5; Parallel-safe: no
- SL-1 - Boundary extraction observability runtime; Depends on: SL-0; Blocks:
  SL-2, SL-3, SL-4, SL-5; Parallel-safe: no
- SL-2 - Boundary CLI summary and output isolation; Depends on: SL-0, SL-1;
  Blocks: SL-3, SL-4, SL-5; Parallel-safe: yes
- SL-3 - Canonical conformance and golden stabilization; Depends on: SL-0,
  SL-1, SL-2; Blocks: SL-4, SL-5; Parallel-safe: no
- SL-4 - Recovery and downstream additive regression anchors; Depends on:
  SL-1, SL-2, SL-3; Blocks: SL-5; Parallel-safe: yes
- SL-5 - Documentation and roadmap synthesis; Depends on: SL-0, SL-1, SL-2,
  SL-3, SL-4; Blocks: (none); Parallel-safe: no

## Lanes

### SL-0 - Observability Contract Audit And Additive-Extension Freeze

- **Scope**: Reconcile the live observability constants, public API shape, and
  later additive extension points before runtime or docs work depends on them.
- **Owned files**: `chunker/boundary/types.py`, `chunker/boundary/__init__.py`, `tests/test_boundary_ir_observability_contract.py`
- **Interfaces provided**: `TIMING_KEYS`, `METRIC_KEYS`,
  `DIAGNOSTIC_STAGES`, `DIAGNOSTIC_SEVERITIES`, `FILE_STATUSES`,
  `extract_boundary_ir(...)` observability signature expectations
- **Interfaces consumed**: existing `BOUNDARY_IR_SCHEMA_VERSION`,
  `BOUNDARY_IR_SEMANTIC_SCHEMA_VERSION`, `SEMANTIC_RESOLVER_API_VERSION`,
  `RESOLUTION_MODES`, `RESOLUTION_STATUSES`
- **Parallel-safe**: no
- **Tasks**:
  - test: audit and tighten the observability contract tests so exact timing
    keys, base metric keys, base run-option keys, file statuses, and stage
    vocabulary are executable and explicit.
  - test: reconcile current drift between live constants and test expectations,
    especially where later semantic support may require additive observability
    documentation instead of silent mismatch.
  - impl: update `chunker/boundary/types.py` only where the current constant set
    or exported vocabulary is inconsistent with the intended Phase 4 contract
    plus additive later-phase extensions.
  - impl: update `chunker/boundary/__init__.py` only if changed constants or
    aliases must remain importable for downstream callers and tests.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_observability_contract.py -q`

### SL-1 - Boundary Extraction Observability Runtime

- **Scope**: Audit and minimally harden the Boundary IR extraction path for
  deterministic diagnostics, stable counters, timing behavior, and default
  continue versus `fail_fast` semantics.
- **Owned files**: `chunker/boundary/adapter.py`, `chunker/symbol_graph.py`, `tests/test_boundary_ir_observability_metrics.py`, `tests/test_boundary_ir_diagnostics.py`, `tests/test_boundary_ir_fail_fast.py`
- **Interfaces provided**: `extract_boundary_ir(..., fail_fast=False,
  include_timings=False)`, `extract_symbol_graph(..., fail_fast=False)`,
  deterministic diagnostic IDs and ordering, stable `failure_buckets`,
  default-continue failure handling
- **Interfaces consumed**: constants from SL-0; existing `chunk_file()`,
  `collect_source_files()`, `extract_symbol_graph()`,
  `canonicalize_boundary_ir()`, incremental entry points, and semantic resolver
  plumbing
- **Parallel-safe**: no
- **Tasks**:
  - test: keep timing tests explicit about default `null` values versus opt-in
    measured values, and prove metrics still match emitted files, nodes, edges,
    and diagnostics.
  - test: keep diagnostics tests deterministic across repeated runs, including
    stable IDs, canonical ordering, file-level diagnostic references, and
    lexicographically stable `failure_buckets`.
  - test: keep `fail_fast=True` coverage for parser, metadata, graph, and
    serialization failures, while default extraction continues and records
    structured diagnostics where possible.
  - impl: fix only the concrete runtime drift the focused tests expose; do not
    re-architect Boundary IR extraction or widen scope into performance tuning.
  - impl: preserve additive incremental and semantic option handling when
    touching run options or diagnostic generation.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_observability_metrics.py tests/test_boundary_ir_diagnostics.py tests/test_boundary_ir_fail_fast.py -q`

### SL-2 - Boundary CLI Summary And Output Isolation

- **Scope**: Freeze the CLI observability behavior so summary/reporting aids do
  not pollute canonical JSON output or drift from the runtime contract.
- **Owned files**: `cli/main.py`, `tests/test_boundary_ir_cli_observability.py`, `tests/test_boundary_ir_cli.py`
- **Interfaces provided**: `boundary --fail-fast`, `boundary --include-timings`,
  `boundary --summary`, fixed-order summary formatting, stdout/stderr separation
- **Interfaces consumed**: SL-1 `extract_boundary_ir(...)` runtime behavior and
  expanded metrics/timing fields
- **Parallel-safe**: yes
- **Tasks**:
  - test: keep CLI tests explicit that stdout remains parseable JSON when no
    output path is used, `--summary` reports via stderr, and output-file mode
    prints the summary only when `--quiet` is not set.
  - test: confirm CLI failure behavior remains nonzero and surfaces the runtime
    exception path when `--fail-fast` is used.
  - impl: fix summary ordering or output-channel drift only where the focused
    CLI tests prove a mismatch.
  - impl: do not widen this lane into non-boundary CLI behavior.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_cli_observability.py tests/test_boundary_ir_cli.py -q`

### SL-3 - Canonical Conformance And Golden Stabilization

- **Scope**: Reconcile conformance helpers, required-field assertions, and
  golden snapshots with the settled observability contract so default canonical
  output remains deterministic.
- **Owned files**: `tests/boundary_ir_conformance.py`, `tests/test_boundary_ir_required_fields.py`, `tests/test_boundary_ir_determinism.py`, `tests/test_boundary_ir_golden_snapshots.py`, `tests/fixtures/boundary_ir/golden/**`
- **Interfaces provided**: updated required-field validation for observability
  keys, deterministic golden snapshots, repeated-run byte-equality for default
  canonical output
- **Interfaces consumed**: SL-0 constants; SL-1 runtime behavior; SL-2 CLI
  output constraints where they affect conformance helpers or smoke coverage
- **Parallel-safe**: no
- **Tasks**:
  - test: update required-field helpers only after SL-0 and SL-1 settle the
    exact observability contract for `metrics`, `run.options`, and
    `run.timings`.
  - test: keep determinism coverage focused on default canonical output, with
    timing values still `null` unless `include_timings=True`.
  - impl: update golden JSON only after contract and runtime behavior are
    settled; do not normalize observability fields beyond the existing
    `run.tool_version` sentinel.
  - impl: leave `scripts/run_ci_smoke.py` unchanged unless the existing smoke
    batch no longer covers the settled observability-sensitive conformance path.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_required_fields.py tests/test_boundary_ir_determinism.py tests/test_boundary_ir_golden_snapshots.py -q`

### SL-4 - Recovery And Downstream Additive Regression Anchors

- **Scope**: Preserve resilience and later additive-phase guarantees while
  observability drift is repaired.
- **Owned files**: `tests/test_recovery.py`, `tests/test_parallel_error_handling.py`, `tests/test_boundary_ir_cli_incremental.py`, `tests/test_boundary_ir_incremental_contract.py`, `tests/test_boundary_ir_semantic_contract.py`, `tests/test_boundary_ir_semantic_determinism.py`
- **Interfaces provided**: regression anchors for partial-result preservation,
  downstream incremental option stability, and additive semantic determinism
- **Interfaces consumed**: settled failure semantics from SL-1; CLI behavior
  from SL-2; conformance/golden expectations from SL-3
- **Parallel-safe**: yes
- **Tasks**:
  - test: keep or tighten focused recovery assertions that successful files
    still survive neighboring extraction failures when `fail_fast=False`.
  - test: add incremental or semantic regression assertions only where
    observability-facing changes expose drift in option plumbing, diagnostics,
    or canonical determinism.
  - impl: avoid production edits in this lane; if a code change is required,
    move that requirement back to the owning producer lane.
  - verify: `uv run --with toml --all-extras pytest tests/test_recovery.py tests/test_parallel_error_handling.py tests/test_boundary_ir_cli_incremental.py tests/test_boundary_ir_incremental_contract.py tests/test_boundary_ir_semantic_contract.py tests/test_boundary_ir_semantic_determinism.py -q`

### SL-5 - Documentation And Roadmap Synthesis

- **Scope**: Update the human-readable observability contract after the
  producer lanes settle the exact live behavior.
- **Owned files**: `docs/interface-boundary-spec.md`, `docs/interface-boundary-roadmap.md`, `docs/agent-interface-readiness.md`, `docs/cli-reference.md`, `docs/user-guide.md`, `docs/getting-started.md`, `docs/performance-guide.md`
- **Interfaces provided**: docs that match the settled observability contract
  for timings, metrics, diagnostics, failure semantics, and CLI summary
  behavior
- **Interfaces consumed**: SL-0 through SL-4 constants, runtime behavior, CLI
  output rules, conformance decisions, and downstream regression findings
- **Parallel-safe**: no
- **Tasks**:
  - test: review docs against executable tests and add no docs-only assertions
    unless a concrete observability rule lacks an executable anchor.
  - impl: update the interface spec with the finalized observability key sets,
    deterministic diagnostic rules, default `null` timings behavior, and any
    additive semantic-stage clarification required by the settled contract.
  - impl: update CLI docs for `--fail-fast`, `--include-timings`, `--summary`,
    and output-file versus `--quiet` summary behavior.
  - impl: update readiness and roadmap docs only where current status or
    implemented-observability prose has drifted from the live code and tests.
  - impl: do not widen docs into incremental implementation work, semantic
    feature work, external telemetry, or ownership-policy behavior.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_observability_contract.py tests/test_boundary_ir_observability_metrics.py tests/test_boundary_ir_diagnostics.py tests/test_boundary_ir_fail_fast.py tests/test_boundary_ir_cli_observability.py tests/test_boundary_ir_required_fields.py tests/test_boundary_ir_determinism.py tests/test_boundary_ir_golden_snapshots.py tests/test_boundary_ir_cli_incremental.py tests/test_boundary_ir_incremental_contract.py tests/test_boundary_ir_semantic_contract.py tests/test_boundary_ir_semantic_determinism.py -q`
  - verify: `uv run --with toml --all-extras mkdocs build --strict`

## Verification

Planning wrote the artifact only; verification was not run. During execution,
run the phase-focused checks first, then the repo-standard local CI loop from
`AGENTS.md`:

```bash
uv run --with toml --all-extras pytest tests/test_boundary_ir_observability_contract.py tests/test_boundary_ir_observability_metrics.py tests/test_boundary_ir_diagnostics.py tests/test_boundary_ir_fail_fast.py tests/test_boundary_ir_cli_observability.py tests/test_boundary_ir_required_fields.py tests/test_boundary_ir_determinism.py tests/test_boundary_ir_golden_snapshots.py -q
uv run --with toml --all-extras pytest tests/test_recovery.py tests/test_parallel_error_handling.py tests/test_boundary_ir_cli_incremental.py tests/test_boundary_ir_incremental_contract.py tests/test_boundary_ir_semantic_contract.py tests/test_boundary_ir_semantic_determinism.py -q
uv run --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
uv run --all-extras black --check chunker/ cli/ tests/ scripts/
uv run --with toml --all-extras python scripts/run_ci_smoke.py
uv run --with toml --all-extras mkdocs build --strict
```

Because this phase touches canonical JSON shape, CLI output behavior, parser
failure handling, and path-sensitive docs/test surfaces, run the standing
Windows preflight before pushing:

```bash
ssh leno 'powershell -NoProfile -Command "cd $HOME\\code\\treesitter-chunker; git fetch origin; git checkout main; git pull --ff-only; uv run --with toml --all-extras python scripts/run_windows_preflight.py"'
```

## Acceptance Criteria

- [ ] The uppercase execution artifact
  `plans/phase-plan-v1-OBSERVABILITY.md` is the authoritative OBSERVABILITY
  plan for this phase-loop run, and the lowercase historical artifact is not
  used as the execution target.
- [ ] The live observability contract is reconciled across code, focused tests,
  docs, and golden fixtures without regressing additive incremental or semantic
  option plumbing.
- [ ] `run.timings` remains frozen to `parse_ms`,
  `metadata_normalization_ms`, `graph_assembly_ms`, `resolution_ms`,
  `serialization_ms`, and `total_ms`, with default `null` values and opt-in
  nonnegative numeric timings.
- [ ] Base `run.options` and `metrics` keys are documented and tested exactly,
  and any semantic-specific observability fields are clearly treated as
  additive.
- [ ] Diagnostic records keep deterministic IDs and stable canonical ordering,
  and failure buckets remain deterministic code-to-count mappings.
- [ ] Default extraction continues on parser, metadata, graph, and
  serialization failures where partial results are still valid, while
  `fail_fast=True` raises on the first such failure and returns no partial IR.
- [ ] The `boundary` CLI preserves parseable stdout JSON and exposes
  `--fail-fast`, `--include-timings`, and `--summary` with stable summary
  routing and ordering.
- [ ] Required-field helpers, determinism tests, and checked golden snapshots
  all reflect the settled observability contract without normalizing fields
  beyond `run.tool_version`.
- [ ] Recovery, incremental, and semantic regression anchors remain green or
  are updated only where a real observability-contract drift requires it.
- [ ] Phase 4 remains bounded to diagnostics and run observability; it does not
  widen into new incremental algorithms, semantic feature work, external
  telemetry integration, or ownership-policy enforcement.
