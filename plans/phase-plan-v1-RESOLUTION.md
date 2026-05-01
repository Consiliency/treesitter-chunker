---
phase_loop_plan_version: 1
phase: RESOLUTION
roadmap: specs/phase-plans-v1.md
roadmap_sha256: 60b1380b9de14b340499012c1e99f930e5f0ec91613b8ce57a3ea0297f62d4e7
---

# RESOLUTION: Deterministic Resolution Modes

## Context

Roadmap source: `specs/phase-plans-v1.md`, Phase 2 (`RESOLUTION`). Canonical
`.phase-loop/state.json` marks `RESOLUTION` as `unplanned`. The repo itself is
now clean on `main` at `9846dd91`, and it is materially ahead of the original
Phase 2 sequencing: shared resolution vocabulary, strict/permissive mode
plumbing, CLI flags, docs references, and focused tests already exist across
`chunker/boundary/`, `chunker/symbol_graph.py`, `cli/main.py`, and dedicated
resolution test files.

RESOLUTION execution should not replay the original feature build from scratch.
It should freeze the current resolution surface against the live code, close
any contract drift between symbol graph output, Boundary IR edge mapping, CLI
behavior, and docs, and make only the smallest production adjustments needed to
keep strict policy-safe output and permissive discovery output explicit and
deterministic.

This phase remains bounded to relationship classification, strict/permissive
mode defaults, candidate-set determinism, Boundary IR target/provenance
semantics, and compatibility for existing symbol-graph consumers. It must not
widen into observability redesign, incremental-cache behavior changes, semantic
resolver behavior, broader conformance-fixture expansion, or ownership-policy
logic.

The older lowercase artifact was removed to avoid case-insensitive filesystem
collisions. Phase-loop execution for this run should follow this uppercase
`plans/phase-plan-v1-RESOLUTION.md` artifact.

## Interface Freeze Gates

- [ ] IF-0-RESOLUTION-3 — Relationship resolution contract exposes
  `resolved`, `ambiguous`, and `unresolved` states with strict/permissive mode
  semantics.
- [ ] IF-0-RESOLUTION-3A — Shared resolution vocabulary is frozen at
  `ResolutionStatus = Literal["resolved", "ambiguous", "unresolved"]` and
  `ResolutionMode = Literal["strict", "permissive"]`, exported from
  `chunker.boundary` and consumed consistently by symbol-graph and Boundary IR
  surfaces.
- [ ] IF-0-RESOLUTION-3B — `extract_symbol_graph(path, language=None,
  resolution_mode="permissive", fail_fast=False)` preserves legacy
  relationship fields `from`, `to`, `type`, `line`, `file`, and `is_internal`
  while additively exposing `reference`, `resolution`, `candidates`,
  `resolution_mode`, and syntax provenance.
- [ ] IF-0-RESOLUTION-3C — Candidate classification is deterministic: one
  candidate is `resolved`, multiple sorted candidates are `ambiguous`, and zero
  candidates are `unresolved`, without changing the public top-level graph
  shape.
- [ ] IF-0-RESOLUTION-3D — `extract_boundary_ir(path, language=None, *,
  canonical=True, created_at=None, resolution_mode="strict", ...)` emits no
  guessed target node identity for `ambiguous` or `unresolved` edges; emitted
  `metrics` and `run.options.resolution_mode` match the actual edge statuses
  and mode used.
- [ ] IF-0-RESOLUTION-3E — CLI contracts are frozen at
  `treesitter-chunker boundary --resolution-mode strict|permissive` and
  `python -m chunker.cli symbols extract --resolution-mode strict|permissive`,
  while `cluster infer` stays explicitly discovery-oriented.
- [ ] IF-0-RESOLUTION-3F — Docs and focused tests describe and enforce the live
  resolution contract without reopening SCHEMA-owned base-schema work or
  widening into later observability, incremental, semantic, or conformance
  phases.

## Lane Index & Dependencies

- SL-0 — Shared resolution vocabulary and symbol-graph contract; Depends on:
  (none); Blocks: SL-1, SL-2, SL-3; Parallel-safe: no
- SL-1 — Boundary IR resolution mapping and counters; Depends on: SL-0;
  Blocks: SL-2, SL-3; Parallel-safe: yes
- SL-2 — CLI and legacy consumer compatibility; Depends on: SL-0, SL-1;
  Blocks: SL-3; Parallel-safe: mixed
- SL-3 — Resolution docs and phase synthesis; Depends on: SL-0, SL-1, SL-2;
  Blocks: (none); Parallel-safe: no

## Lanes

### SL-0 — Shared Resolution Vocabulary And Symbol-Graph Contract

- **Scope**: Freeze the live symbol-graph resolution surface so candidate
  classification, defaults, and additive fields are explicit and consistent
  with the exported Boundary IR vocabulary.
- **Owned files**: `chunker/symbol_graph.py`, `tests/test_boundary_resolution_contract.py`, `tests/test_symbol_graph_resolution.py`, `tests/test_symbol_graph.py`
- **Interfaces provided**: IF-0-RESOLUTION-3A, IF-0-RESOLUTION-3B,
  IF-0-RESOLUTION-3C; deterministic relationship classification for
  `extract_symbol_graph()`
- **Interfaces consumed**: `ResolutionMode`, `ResolutionStatus`,
  `RESOLUTION_MODES`, and `RESOLUTION_STATUSES` from `chunker.boundary`;
  symbol facts from `extract_symbol_facts_for_file()` and
  `assemble_symbol_graph()`
- **Parallel-safe**: no
- **Tasks**:
  - test: audit the live `extract_symbol_graph()` relationship shape and
    defaults against the roadmap exit criteria, separating already-implemented
    contract surface from any remaining drift.
  - test: tighten focused coverage for duplicate-name ambiguity, missing-target
    unresolved references, unique resolved references, deterministic candidate
    sorting, and backward-compatible `is_internal` behavior.
  - impl: if execution finds duplicated literal definitions or validation drift
    between `chunker.symbol_graph` and `chunker.boundary`, consolidate on the
    shared exported vocabulary without changing the permissive default or the
    public graph envelope.
  - impl: keep `symbols`, `relationships`, `metadata`, `symbol_lookup`, and
    `errors` stable; do not widen this lane into semantic-resolution or
    non-core graph redesign.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_resolution_contract.py tests/test_symbol_graph_resolution.py tests/test_symbol_graph.py -q`

### SL-1 — Boundary IR Resolution Mapping And Counters

- **Scope**: Freeze the Boundary IR adapter's strict/permissive edge semantics,
  emitted targets, provenance, and edge-status counters against the current
  symbol-graph contract.
- **Owned files**: `chunker/boundary/adapter.py`, `tests/test_boundary_ir_resolution_modes.py`, `tests/test_boundary_ir_adapter.py`, `tests/test_boundary_ir_contract.py`
- **Interfaces provided**: IF-0-RESOLUTION-3 and IF-0-RESOLUTION-3D; strict
  Boundary IR edge mapping and counter semantics
- **Interfaces consumed**: relationship fields from SL-0;
  `extract_boundary_ir()`, `_edge_record()`, and metric keys from
  `chunker.boundary`
- **Parallel-safe**: yes
- **Tasks**:
  - test: tighten strict-mode and permissive-mode coverage around
    ambiguous/unresolved targets, deterministic candidate ordering,
    `run.options.resolution_mode`, strict provenance, and counter parity with
    emitted edges.
  - test: confirm the default Boundary IR contract remains
    `resolution_mode="strict"` while syntax-only output stays on
    `schema_version == "1.0"` unless optional semantic resolvers are supplied.
  - impl: make only the minimal adapter changes needed if current edge mapping,
    target selection, or metric counting diverges from the frozen resolution
    contract.
  - impl: preserve observability, incremental, and semantic options as additive
    downstream surfaces; do not redesign them in this phase.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_resolution_modes.py tests/test_boundary_ir_adapter.py tests/test_boundary_ir_contract.py -q`

### SL-2 — CLI And Legacy Consumer Compatibility

- **Scope**: Freeze user-facing mode selection for Boundary IR and symbol-graph
  commands while preserving discovery-oriented legacy consumers.
- **Owned files**: `cli/main.py`, `chunker/cli/symbol_commands.py`, `chunker/cli/cluster_commands.py`, `tests/test_boundary_ir_cli.py`, `tests/test_symbol_graph_cli_resolution.py`
- **Interfaces provided**: IF-0-RESOLUTION-3E; CLI option pass-through and
  backward-compatible JSON-oriented behavior
- **Interfaces consumed**: `extract_boundary_ir()` from SL-1;
  `extract_symbol_graph()` from SL-0; existing Typer and argparse command
  conventions
- **Parallel-safe**: mixed
- **Tasks**:
  - test: tighten boundary CLI coverage for default strict mode, explicit
    permissive mode, stdout-only JSON behavior, file-output summary behavior,
    and non-regression for existing JSON-oriented commands.
  - test: tighten symbol CLI coverage for `--resolution-mode` while preserving
    legacy relationship fields; keep `cluster infer` explicitly permissive and
    ensure additive resolution fields survive its post-processing.
  - impl: adjust CLI plumbing only where live behavior diverges from the frozen
    defaults or option pass-through contract.
  - impl: do not redesign unrelated CLI command families or output formats in
    this phase.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_cli.py tests/test_symbol_graph_cli_resolution.py tests/test_cli.py -q`

### SL-3 — Resolution Docs And Phase Synthesis

- **Scope**: Align the human-readable resolution contract with the frozen live
  behavior after code and CLI lanes settle the exact semantics.
- **Owned files**: `docs/interface-boundary-spec.md`, `docs/interface-boundary-roadmap.md`, `docs/cli-reference.md`, `docs/user-guide.md`
- **Interfaces provided**: IF-0-RESOLUTION-3F; explicit docs for strict versus
  permissive resolution semantics and current CLI behavior
- **Interfaces consumed**: all interfaces from SL-0, SL-1, and SL-2
- **Parallel-safe**: no
- **Tasks**:
  - test: audit the current docs against the actual live behavior frozen by the
    earlier lanes, treating implemented resolution features as present reality
    rather than future roadmap prose.
  - impl: document the additive resolution extension in
    `docs/interface-boundary-spec.md` without reopening SCHEMA-owned base-schema
    sections.
  - impl: update `docs/interface-boundary-roadmap.md`, `docs/cli-reference.md`,
    and `docs/user-guide.md` so strict Boundary IR defaults, permissive symbol
    graph defaults, ambiguous/unresolved target behavior, and mode/counter
    semantics are explicit and consistent.
  - impl: do not widen this lane into observability, incremental, semantic, or
    broad conformance-doc work beyond the references needed to explain the
    resolution contract.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_resolution_contract.py tests/test_symbol_graph_resolution.py tests/test_boundary_ir_resolution_modes.py tests/test_boundary_ir_cli.py tests/test_symbol_graph_cli_resolution.py -q`
  - verify: `uv run --with toml --all-extras mkdocs build --strict`

## Verification

Planning wrote the artifact only; verification was not run. During execution,
run the phase-focused checks first, then the repo-standard local CI smoke:

```bash
uv run --with toml --all-extras pytest tests/test_boundary_resolution_contract.py tests/test_symbol_graph_resolution.py tests/test_boundary_ir_resolution_modes.py tests/test_boundary_ir_adapter.py tests/test_boundary_ir_contract.py tests/test_boundary_ir_cli.py tests/test_symbol_graph_cli_resolution.py -q
uv run --with toml --all-extras pytest tests/test_symbol_graph.py tests/test_relationship_tracker.py tests/test_boundary_ir_language_parity.py -q
uv run --with toml --all-extras mkdocs build --strict
uv run --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
uv run --all-extras black --check chunker/ cli/ tests/ scripts/
uv run --with toml --all-extras python scripts/run_ci_smoke.py
```

Because this phase touches extraction behavior, CLI mode plumbing, and emitted
JSON semantics, run the standing Windows preflight before pushing:

```bash
ssh win 'powershell -NoProfile -Command "cd $HOME\\code\\treesitter-chunker; git fetch origin; git checkout main; git pull --ff-only; uv run --with toml --all-extras python scripts/run_windows_preflight.py"'
```

## Acceptance Criteria

- [ ] Shared resolution vocabulary is exact and consistent across exported
  Boundary IR and symbol-graph surfaces.
- [ ] `extract_symbol_graph()` keeps permissive mode as the compatible default,
  preserves legacy relationship fields, and additively emits deterministic
  `reference`, `resolution`, `candidates`, `resolution_mode`, and provenance
  data.
- [ ] Candidate classification remains deterministic: one candidate resolves,
  multiple candidates are sorted and ambiguous, and zero candidates are
  unresolved.
- [ ] `extract_boundary_ir()` keeps strict mode as the default, emits no guessed
  target identity for ambiguous or unresolved edges, and records matching
  counters plus `run.options.resolution_mode`.
- [ ] Boundary IR and symbol CLI surfaces expose deterministic mode selection
  without regressing existing JSON-oriented flows, and `cluster infer` remains
  explicitly discovery-oriented.
- [ ] Docs describe the current strict/permissive semantics and target/counter
  behavior without reopening the SCHEMA base contract or widening into later
  phases.
- [ ] Focused symbol-graph, Boundary IR, and CLI tests enforce the frozen
  resolution contract.
- [ ] RESOLUTION execution does not redesign observability, incremental,
  semantic, or broad conformance surfaces.
