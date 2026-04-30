---
phase_loop_plan_version: 1
phase: ADAPTER
roadmap: specs/phase-plans-v1.md
roadmap_sha256: 60b1380b9de14b340499012c1e99f930e5f0ec91613b8ce57a3ea0297f62d4e7
---

# ADAPTER: Canonical Boundary IR Adapter

## Context

Roadmap source: `specs/phase-plans-v1.md`, Phase 1 (`ADAPTER`). Canonical
`.phase-loop/` state still marks `ADAPTER` as `unplanned`, while the repo is
currently clean on `main` at `8d61fb40` after the prior `SCHEMA` closeout.

This repository is materially ahead of the original Phase 1 roadmap. The
public Boundary IR adapter already exists under `chunker/boundary/`, the Typer
CLI already exposes `boundary`, canonical serialization/export helpers already
exist, and later phases have already added resolution-mode, observability,
incremental, and semantic-enrichment surfaces. ADAPTER execution should not try
to rewind that implementation history or repartition later work back into Phase
1. It should freeze the Phase 1 adapter contract against the current code,
tighten the focused tests and docs that define the syntax-first adapter
baseline, and make only the bounded production adjustments needed to keep the
Phase 1 surface explicit and execution-ready.

This phase remains limited to the canonical adapter layer that turns
`chunk_file(..., extract_metadata=True, include_retrieval_metadata=True)` plus
`extract_symbol_graph()` output into the frozen Boundary IR schema, together
with its canonical serializer, export helper, public Python API, and packaged
CLI entry point. It must not broaden into redesigning strict/permissive
resolution semantics, observability counters/timings, incremental cache
behavior, semantic resolver policy, or ownership enforcement.

The older lowercase artifact `plans/phase-plan-v1-adapter.md` exists as
historical planning context only. Phase-loop execution for this run should
follow this uppercase `plans/phase-plan-v1-ADAPTER.md` artifact.

## Interface Freeze Gates

- [ ] IF-0-ADAPTER-1 - The public Python adapter remains callable at both
  `chunker.boundary.extract_boundary_ir` and `chunker.extract_boundary_ir`, and
  syntax-only output uses `schema_version == "1.0"` when semantic resolvers are
  not supplied.
- [ ] IF-0-ADAPTER-2 - The adapter continues to assemble Boundary IR from
  `chunk_file(..., extract_metadata=True, include_retrieval_metadata=True)` and
  `extract_symbol_graph()` without regressing existing chunking or symbol-graph
  behavior.
- [ ] IF-0-ADAPTER-3 - Deterministic node identity and deduplication remain
  frozen around `definition_id` -> `module + qualified_name` -> `node_id`,
  with canonical node IDs and stable file/node/edge ordering in emitted output.
- [ ] IF-0-ADAPTER-4 - Canonical JSON output remains frozen at
  `dumps_boundary_ir()` plus `write_boundary_ir()`: UTF-8-compatible text,
  deterministic ordering, compact default serialization, and exactly one
  trailing newline.
- [ ] IF-0-ADAPTER-5 - The packaged CLI contract remains
  `treesitter-chunker boundary <path> --lang <language> [--output <file>] [--pretty]`
  with canonical JSON written to stdout when `--output` is omitted.
- [ ] IF-0-ADAPTER-6 - Default adapter output omits volatile timestamps unless
  the caller supplies `created_at`, and canonical repo/file outputs remain
  double-run deterministic for identical inputs.
- [ ] IF-0-ADAPTER-7 - Later surfaces already present in the signature or CLI
  (`resolution_mode`, `fail_fast`, `include_timings`, `incremental`,
  `semantic_resolvers`, related cache options) are preserved as additive
  downstream extensions and are not redefined by ADAPTER execution.
- [ ] IF-0-ADAPTER-8 - Focused adapter, serialization, CLI, and contract tests
  cover the Phase 1 surface while existing legacy JSON export and symbol-graph
  tests continue to pass.

## Lane Index & Dependencies

- SL-0 - Public adapter surface normalization; Depends on: (none); Blocks:
  SL-1, SL-2, SL-3; Parallel-safe: no
- SL-1 - Canonical serialization and export compatibility; Depends on: SL-0;
  Blocks: SL-2, SL-3; Parallel-safe: yes
- SL-2 - Boundary CLI contract; Depends on: SL-0, SL-1; Blocks: SL-3;
  Parallel-safe: no
- SL-3 - Adapter contract coverage and docs synthesis; Depends on: SL-0, SL-1,
  SL-2; Blocks: (none); Parallel-safe: no

## Lanes

### SL-0 - Public Adapter Surface Normalization

- **Scope**: Normalize the current adapter entry points and base output contract
  so Phase 1 is explicit in the production surface without reopening later
  phases.
- **Owned files**: `chunker/boundary/adapter.py`, `chunker/boundary/__init__.py`, `chunker/__init__.py`, `tests/test_boundary_ir_adapter.py`
- **Interfaces provided**: IF-0-ADAPTER-1, IF-0-ADAPTER-2, IF-0-ADAPTER-3,
  IF-0-ADAPTER-6; stable `extract_boundary_ir()` baseline behavior for file and
  repository paths; public package re-export contract
- **Interfaces consumed**: `chunk_file()` from `chunker/core.py`;
  `extract_symbol_graph()` and `collect_source_files()` from
  `chunker/symbol_graph.py`; identity helpers and schema constants from
  `chunker/boundary/types.py`; SCHEMA contract from
  `docs/interface-boundary-spec.md`
- **Parallel-safe**: no
- **Tasks**:
  - test: audit the live `extract_boundary_ir()` signature and behavior against
    the roadmap exit criteria, separating the syntax-first Phase 1 baseline
    from already-implemented downstream options.
  - test: tighten `tests/test_boundary_ir_adapter.py` around deterministic
    file-path handling, identity precedence, unresolved/resolved edge mapping,
    repo-versus-file input behavior, and `created_at is None` by default.
  - impl: keep `extract_boundary_ir()` public at both package entry points and
    make only the smallest production changes needed to keep the base adapter
    behavior explicit and deterministic.
  - impl: preserve the current use of `chunk_file(..., extract_metadata=True,
    include_retrieval_metadata=True)` and `extract_symbol_graph()` as the
    adapter substrate; do not rewrite resolver internals in this phase.
  - impl: treat `resolution_mode`, observability, incremental, and semantic
    options as additive passthrough surfaces unless a bug directly breaks the
    base adapter contract.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_adapter.py tests/test_definition_id.py tests/test_metadata_extraction.py -q`

### SL-1 - Canonical Serialization And Export Compatibility

- **Scope**: Freeze the canonical Boundary IR JSON serializer and export helper
  against the current adapter output without changing legacy JSON exporter
  contracts.
- **Owned files**: `chunker/boundary/serialization.py`, `chunker/export/boundary_ir.py`, `chunker/export/__init__.py`, `tests/test_boundary_ir_serialization.py`
- **Interfaces provided**: IF-0-ADAPTER-4; `canonicalize_boundary_ir()`;
  `dumps_boundary_ir()`; `write_boundary_ir()`; `BoundaryIRExporter`
- **Interfaces consumed**: adapter output from SL-0; schema ordering and
  canonical JSON rules from `docs/interface-boundary-spec.md`
- **Parallel-safe**: yes
- **Tasks**:
  - test: tighten serialization coverage for deterministic ordering of
    `files`, `nodes`, `edges`, `diagnostics`, and nested string-ID lists that
    affect output equality.
  - test: verify compact output, exactly one trailing newline, and UTF-8 file
    writes using explicit `encoding="utf-8"`.
  - test: keep legacy export compatibility covered by exercising existing JSON
    exporter tests instead of widening this lane into unrelated format changes.
  - impl: make only focused canonicalization or export-helper fixes required to
    match the frozen serializer contract.
  - impl: do not repurpose `JSONExporter`, `JSONLExporter`, or other legacy
    exporters into the canonical Boundary IR surface.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_serialization.py tests/test_export_json.py tests/test_export_jsonl.py -q`

### SL-2 - Boundary CLI Contract

- **Scope**: Freeze the packaged `boundary` CLI command around the current
  adapter/export surface while protecting pre-existing CLI behavior.
- **Owned files**: `cli/main.py`, `tests/test_boundary_ir_cli.py`
- **Interfaces provided**: IF-0-ADAPTER-5 and the CLI portion of
  IF-0-ADAPTER-7; stdout/file-output behavior for `boundary`
- **Interfaces consumed**: `extract_boundary_ir()` from SL-0;
  `dumps_boundary_ir()` and `write_boundary_ir()` from SL-1; existing Typer app
  conventions in `cli/main.py`
- **Parallel-safe**: no
- **Tasks**:
  - test: tighten `CliRunner` coverage for stdout JSON, file-output JSON,
    default strict-mode options, and additive CLI flags that must remain
    non-breaking.
  - test: keep compatibility assertions for existing `chunk --json` and
    `batch --output-format json` behavior so Phase 1 does not silently regress
    older CLI surfaces.
  - impl: adjust the `boundary` command only where the live behavior diverges
    from the frozen adapter/export contract.
  - impl: keep stdout pure JSON when `--output` is omitted; keep concise human
    output only for file-writing flows unless `--quiet` suppresses it.
  - impl: leave the legacy argparse symbol CLI untouched unless a concrete
    regression in shared CLI plumbing is uncovered during execution.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_cli.py tests/test_cli.py tests/test_cli_integration_advanced.py -q`

### SL-3 - Adapter Contract Coverage And Docs Synthesis

- **Scope**: Tighten the phase-owned contract tests and minimal docs so the
  current Phase 1 adapter story is explicit and consistent with the roadmap.
- **Owned files**: `tests/test_boundary_ir_contract.py`, `docs/interface-boundary-roadmap.md`, `docs/user-guide.md`
- **Interfaces provided**: IF-0-ADAPTER-8; explicit Phase 1 contract wording
  and adapter-level acceptance coverage
- **Interfaces consumed**: all interfaces from SL-0, SL-1, and SL-2; canonical
  schema wording from `docs/interface-boundary-spec.md`
- **Parallel-safe**: no
- **Tasks**:
  - test: tighten `tests/test_boundary_ir_contract.py` around top-level keys,
    required file/node/run fields, syntax-only schema version, and stable
    canonical output for a small fixture.
  - test: use existing golden/required-field suites as verification consumers;
    do not duplicate later-phase resolution, observability, incremental, or
    semantic coverage in this lane.
  - impl: update `docs/interface-boundary-roadmap.md` so the adapter work item
    and exit criteria clearly point at the current canonical adapter surface
    while keeping later implemented capabilities labeled as downstream work.
  - impl: add or tighten a minimal `docs/user-guide.md` Boundary IR example if
    the current CLI/API examples do not clearly match the frozen Phase 1
    contract.
  - impl: do not edit `docs/interface-boundary-spec.md` in this phase unless
    execution finds a true schema ambiguity that blocks the adapter contract;
    such a change would require stopping for scope review because SCHEMA owns
    the base spec.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_contract.py tests/test_boundary_ir_golden_snapshots.py tests/test_boundary_ir_required_fields.py -q`
  - verify: `uv run --with toml --all-extras mkdocs build --strict`

## Verification

Planning wrote the artifact only; verification was not run. During execution,
run the phase-focused checks first, then the repo-standard local CI smoke:

```bash
uv run --with toml --all-extras pytest tests/test_boundary_ir_adapter.py tests/test_boundary_ir_serialization.py tests/test_boundary_ir_cli.py tests/test_boundary_ir_contract.py -q
uv run --with toml --all-extras pytest tests/test_definition_id.py tests/test_metadata_extraction.py tests/test_symbol_graph.py tests/test_export_json.py tests/test_export_jsonl.py tests/test_boundary_ir_golden_snapshots.py tests/test_boundary_ir_required_fields.py -q
uv run --with toml --all-extras mkdocs build --strict
uv run --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
uv run --all-extras black --check chunker/ cli/ tests/ scripts/
uv run --with toml --all-extras python scripts/run_ci_smoke.py
```

Because this phase touches CLI paths, serialization, and output formatting, run
the standing Windows preflight before pushing:

```bash
ssh leno 'powershell -NoProfile -Command "cd $HOME\\code\\treesitter-chunker; git fetch origin; git checkout main; git pull --ff-only; uv run --with toml --all-extras python scripts/run_windows_preflight.py"'
```

## Acceptance Criteria

- [ ] `extract_boundary_ir()` remains a public Boundary IR entry point at both
  `chunker.boundary` and top-level `chunker`.
- [ ] Syntax-only adapter output uses `schema_version == "1.0"` when semantic
  resolvers are not supplied.
- [ ] The adapter continues to derive Boundary IR from
  `chunk_file(..., extract_metadata=True, include_retrieval_metadata=True)` and
  `extract_symbol_graph()` without regressing existing chunking or symbol-graph
  behavior.
- [ ] Nodes and edges remain deterministically deduplicated and canonically
  ordered using the frozen identity and serialization rules.
- [ ] Canonical JSON output is deterministic, compact by default,
  UTF-8-compatible, and ends with exactly one trailing newline.
- [ ] `treesitter-chunker boundary` can emit canonical JSON to stdout or a
  requested output file without regressing other JSON-oriented CLI commands.
- [ ] Default output keeps `run.created_at` stable by leaving it unset unless a
  caller provides a deterministic value.
- [ ] Focused adapter, serialization, CLI, and contract tests cover the Phase
  1 surface, while legacy JSON export and symbol-graph tests continue to pass.
- [ ] ADAPTER execution does not redesign strict/permissive resolution
  semantics, observability runtime, incremental cache behavior, semantic
  resolver policy, or ownership enforcement.
