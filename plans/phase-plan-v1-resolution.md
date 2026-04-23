# RESOLUTION: Deterministic Resolution Modes

## Context

Roadmap source: `specs/phase-plans-v1.md`, Phase 2. The roadmap is currently staged as a new file (`A  specs/phase-plans-v1.md`), so it is not an untracked `git clean -fd` risk.

Phase 0 and Phase 1 artifacts are present in this working tree: `docs/interface-boundary-spec.md` defines the Boundary IR edge keys and counters, while `chunker/boundary/adapter.py` already maps `extract_symbol_graph()` relationships into Boundary IR edges. The current adapter only distinguishes `resolved` from `unresolved` via `relationship["is_internal"]`; `ambiguous_edges` is always `0`. The current symbol graph resolver uses qualified-name lookup and unique unqualified-name lookup, so duplicate unqualified matches collapse to "unresolved" instead of surfacing deterministic candidate sets.

The Phase 2 objective is to freeze and implement resolution states without breaking existing symbol graph consumers. Boundary IR should default to strict, policy-safe output. Existing `extract_symbol_graph()` and clustering/symbol CLI consumers should keep discovery-compatible defaults while receiving additive resolution fields.

## Interface Freeze Gates

- [ ] IF-0-RESOLUTION-3 — Relationship resolution contract exposes `resolved`, `ambiguous`, and `unresolved` states with strict/permissive mode semantics.
- [ ] IF-0-RESOLUTION-3A — Public resolution values are exactly `ResolutionStatus = Literal["resolved", "ambiguous", "unresolved"]` and `ResolutionMode = Literal["strict", "permissive"]`, exported from `chunker.boundary`.
- [ ] IF-0-RESOLUTION-3B — `extract_symbol_graph(path, language=None, resolution_mode="permissive")` remains backward-compatible and every relationship keeps `from`, `to`, `type`, `line`, `file`, and `is_internal` while additively exposing `reference`, `resolution`, `candidates`, `resolution_mode`, and deterministic syntax provenance.
- [ ] IF-0-RESOLUTION-3C — Candidate classification is deterministic: exactly one candidate is `resolved`, multiple candidates are `ambiguous`, and zero candidates are `unresolved`; candidate IDs are sorted lexicographically before emission.
- [ ] IF-0-RESOLUTION-3D — `extract_boundary_ir(path, language=None, *, canonical=True, created_at=None, resolution_mode="strict")` emits no guessed target node ID for `ambiguous` or `unresolved` edges; those edge `target` values are the normalized reference string and `candidates` carries possible node IDs only when available.
- [ ] IF-0-RESOLUTION-3E — Boundary IR `metrics` counts `resolved_edges`, `ambiguous_edges`, and `unresolved_edges` from emitted edge statuses, and `run.options.resolution_mode` records the mode that shaped output.

## Lane Index & Dependencies

- SL-0 — Resolution contract preamble; Depends on: (none); Blocks: SL-1, SL-2, SL-3, SL-4; Parallel-safe: no
- SL-1 — Symbol graph candidate resolver; Depends on: SL-0; Blocks: SL-2, SL-3, SL-4; Parallel-safe: yes
- SL-2 — Boundary IR strict/permissive edge mapping; Depends on: SL-0, SL-1; Blocks: SL-3, SL-4; Parallel-safe: yes after SL-1
- SL-3 — CLI and legacy consumer compatibility; Depends on: SL-0, SL-1, SL-2; Blocks: SL-4; Parallel-safe: mixed
- SL-4 — Documentation and contract synthesis; Depends on: SL-0, SL-1, SL-2, SL-3; Blocks: (none); Parallel-safe: no

## Lanes

### SL-0 — Resolution Contract Preamble

- **Scope**: Add the shared resolution-mode and resolution-status vocabulary before resolver and adapter work branch from it.
- **Owned files**: `chunker/boundary/types.py`, `chunker/boundary/__init__.py`, `tests/test_boundary_resolution_contract.py`
- **Interfaces provided**: `ResolutionStatus`, `ResolutionMode`, `RESOLUTION_STATUSES`, `RESOLUTION_MODES`
- **Interfaces consumed**: existing `BOUNDARY_IR_SCHEMA_VERSION`, `METRIC_KEYS`, `TOP_LEVEL_KEYS`
- **Parallel-safe**: no
- **Tasks**:
  - test: add `tests/test_boundary_resolution_contract.py` assertions that the exported mode/status values are exact, stable, and include all schema counter names.
  - impl: define the status/mode type aliases and constants in `chunker/boundary/types.py`, then export them from `chunker/boundary/__init__.py`.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_resolution_contract.py tests/test_boundary_ir_contract.py -q`

### SL-1 — Symbol Graph Candidate Resolver

- **Scope**: Refactor relationship resolution in `extract_symbol_graph()` so each reference produces a deterministic candidate set and explicit status while preserving current relationship shape.
- **Owned files**: `chunker/symbol_graph.py`, `tests/test_symbol_graph_resolution.py`
- **Interfaces provided**: `extract_symbol_graph(path, language=None, resolution_mode="permissive")`; relationship fields `reference`, `resolution`, `candidates`, `resolution_mode`, `provenance`
- **Interfaces consumed**: `ResolutionMode`, `ResolutionStatus`
- **Parallel-safe**: yes
- **Tasks**:
  - test: add duplicate-name fixtures where an unqualified call has two possible targets and must emit one `ambiguous` relationship with sorted `candidates`, `to == reference`, and `is_internal is False`.
  - test: add unresolved-reference coverage proving zero candidates emits `unresolved`, empty `candidates`, and preserves the normalized `reference`.
  - test: keep existing resolved-call behavior covered by `tests/test_symbol_graph.py` so `is_internal` remains true for exactly one resolved candidate.
  - impl: replace the current single-target `_build_resolution_indexes()`/`_resolve_reference()` path with candidate-set lookup over qualified names and unqualified names.
  - impl: classify relationship status from candidate count, set `to` to the sole candidate only for `resolved`, otherwise set `to` to the normalized reference string.
  - impl: keep the existing `symbols`, `relationships`, `metadata`, `symbol_lookup`, and `errors` top-level graph shape unchanged.
  - verify: `uv run --with toml --all-extras pytest tests/test_symbol_graph_resolution.py tests/test_symbol_graph.py -q`

### SL-2 — Boundary IR Strict/Permissive Edge Mapping

- **Scope**: Thread resolution mode through Boundary IR generation and map graph relationships into policy-safe edge records and counters.
- **Owned files**: `chunker/boundary/adapter.py`, `tests/test_boundary_ir_resolution_modes.py`
- **Interfaces provided**: `extract_boundary_ir(path, language=None, *, canonical=True, created_at=None, resolution_mode="strict")`; Boundary IR edge provenance fields `resolution_mode` and `enforcement_grade`
- **Interfaces consumed**: `extract_symbol_graph(..., resolution_mode=...)`; graph relationship fields from SL-1; `ResolutionMode`, `ResolutionStatus`
- **Parallel-safe**: yes after SL-1
- **Tasks**:
  - test: add strict-mode Boundary IR coverage for ambiguous duplicate symbols: `resolution == "ambiguous"`, `target == reference`, sorted `candidates`, and `metrics["ambiguous_edges"]` increments.
  - test: add unresolved strict-mode coverage proving no guessed target identity and `metrics["unresolved_edges"]` matches emitted edges.
  - test: add permissive-mode coverage proving `run.options.resolution_mode == "permissive"` and ambiguous/unresolved edges keep discovery reference/provenance without `enforcement_grade`.
  - impl: add a `resolution_mode` keyword to `extract_boundary_ir()` with strict as the Boundary IR default.
  - impl: pass the mode into `extract_symbol_graph()`, consume relationship `resolution` and `candidates`, and stop deriving status solely from `is_internal`.
  - impl: compute `resolved_edges`, `ambiguous_edges`, and `unresolved_edges` by counting emitted edge statuses.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_resolution_modes.py tests/test_boundary_ir_adapter.py tests/test_boundary_ir_serialization.py -q`

### SL-3 — CLI And Legacy Consumer Compatibility

- **Scope**: Expose resolution mode where users generate Boundary IR or symbol JSON, while pinning legacy consumers to compatible discovery semantics.
- **Owned files**: `cli/main.py`, `chunker/cli/symbol_commands.py`, `chunker/cli/cluster_commands.py`, `tests/test_boundary_ir_cli.py`, `tests/test_symbol_graph_cli_resolution.py`
- **Interfaces provided**: Typer `boundary --resolution-mode strict|permissive`; argparse `symbols extract --resolution-mode strict|permissive`
- **Interfaces consumed**: `extract_boundary_ir(..., resolution_mode=...)`; `extract_symbol_graph(..., resolution_mode=...)`; legacy relationship fields `from`, `to`, and `is_internal`
- **Parallel-safe**: mixed
- **Tasks**:
  - test: extend boundary CLI tests to assert the default mode is strict and `--resolution-mode permissive` is reflected in `run.options`.
  - test: add symbol CLI tests proving `symbols extract` accepts `--resolution-mode` and still emits legacy relationship fields.
  - impl: add a constrained `--resolution-mode` option to the Typer `boundary` command and pass it through to `extract_boundary_ir()`.
  - impl: add an argparse `--resolution-mode` option to `symbols extract` and pass it through to `extract_symbol_graph()`.
  - impl: make `cluster infer` explicitly call `extract_symbol_graph(..., resolution_mode="permissive")` and avoid overwriting the additive `resolution`/`candidates` fields during `is_internal` post-processing.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_cli.py tests/test_symbol_graph_cli_resolution.py tests/test_cli.py -q`

### SL-4 — Documentation And Contract Synthesis

- **Scope**: Update docs after implementation lanes settle the exact behavior and record that Phase 2 resolution semantics are frozen.
- **Owned files**: `docs/interface-boundary-spec.md`, `docs/interface-boundary-roadmap.md`, `docs/cli-reference.md`
- **Interfaces provided**: updated human-readable IF-0-RESOLUTION-3 contract and CLI usage docs
- **Interfaces consumed**: SL-0 exported constants, SL-1 graph relationship shape, SL-2 Boundary IR edge mapping, SL-3 CLI flags and defaults
- **Parallel-safe**: no
- **Tasks**:
  - test: review the final behavior tests from SL-0 through SL-3 against the docs and add no docs-only assertions unless a documented required field is uncovered as untested.
  - impl: document strict/permissive mode semantics, candidate classification, `target` behavior for ambiguous/unresolved edges, counters, and `run.options.resolution_mode` in `docs/interface-boundary-spec.md`.
  - impl: update `docs/interface-boundary-roadmap.md` to mark the strict/permissive resolution mode work as implemented or in progress according to repo convention.
  - impl: update `docs/cli-reference.md` for `boundary --resolution-mode` and `symbols extract --resolution-mode`.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_resolution_contract.py tests/test_symbol_graph_resolution.py tests/test_boundary_ir_resolution_modes.py tests/test_boundary_ir_cli.py tests/test_symbol_graph_cli_resolution.py -q`

## Verification

Lane-specific verification is listed in each lane. After all lanes are integrated, run:

```bash
uv run --with toml --all-extras pytest tests/test_boundary_resolution_contract.py tests/test_symbol_graph_resolution.py tests/test_boundary_ir_resolution_modes.py tests/test_boundary_ir_adapter.py tests/test_boundary_ir_cli.py tests/test_symbol_graph_cli_resolution.py tests/test_symbol_graph.py tests/test_relationship_tracker.py -q
uv run --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
uv run --all-extras black --check chunker/ cli/ tests/ scripts/
uv run --with toml --all-extras python scripts/run_ci_smoke.py
```

Because this phase touches extraction and export formatting behavior, run the standing Windows preflight before pushing:

```bash
ssh leno 'powershell -NoProfile -Command "cd $HOME\\code\\treesitter-chunker; git fetch origin; git checkout main; git pull --ff-only; uv run --with toml --all-extras python scripts/run_windows_preflight.py"'
```

## Acceptance Criteria

- [ ] Every Boundary IR edge has `resolution` set to `resolved`, `ambiguous`, or `unresolved`.
- [ ] Strict Boundary IR mode emits no guessed target node identity when an edge is ambiguous or unresolved.
- [ ] Permissive mode preserves discovery-friendly references and provenance without claiming enforcement-grade resolution.
- [ ] Ambiguous and unresolved counters are emitted in Boundary IR `metrics` and match emitted edge statuses.
- [ ] `extract_symbol_graph()` remains compatible for existing consumers or exposes changes only as additive fields behind compatible defaults.
- [ ] Boundary CLI and symbol CLI expose deterministic mode selection, with Boundary IR defaulting to `strict`.
- [ ] Candidate lists and canonical JSON output remain deterministic across repeated runs.
