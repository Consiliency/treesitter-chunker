# ADAPTER: Canonical Boundary IR Adapter

## Context

This plan targets Phase 1 from `specs/phase-plans-v1.md`, resolved from the
selector `P1` as `Phase 1 (ADAPTER)`. It depends on Phase 0's frozen Boundary IR
contract in `docs/interface-boundary-spec.md`.

The roadmap artifact `specs/phase-plans-v1.md` is staged as a new file in this
workspace. The Phase 0 schema artifacts also appear staged or modified and are
treated as existing user work, not as part of this plan.

Phase 1 implements a first-class adapter from current extraction surfaces into
the frozen Boundary IR schema. The existing substrate is:

- `chunker.core.chunk_file(..., extract_metadata=True, include_retrieval_metadata=True)`
  for `CodeChunk` records with `definition_id`, `node_id`, `symbol_id`,
  `file_id`, spans, routes, and normalized retrieval metadata.
- `chunker.symbol_graph.extract_symbol_graph()` for current symbols,
  relationships, import records, resolver output, and parser error summaries.
- `chunker.symbol_graph.collect_source_files()` and language detection patterns
  for file/repository traversal.
- Existing JSON exporters in `chunker/export/`, which should remain compatible
  and should not be repurposed into the canonical Boundary IR contract.
- The packaged Typer CLI in `cli/main.py`, exposed by `treesitter-chunker` and
  `tsc`.

Important constraint: current symbol graph relationships expose `is_internal`
but do not expose ambiguous candidate sets. Phase 1 should emit `resolved` and
`unresolved` states deterministically from current data, preserve provenance, and
leave richer strict/permissive ambiguity semantics to Phase 2.

## Interface Freeze Gates

- [ ] IF-0-ADAPTER-1 -- Public Python API is frozen as
  `chunker.boundary.extract_boundary_ir(path, language=None, *, canonical=True, created_at=None) -> dict[str, Any]`.
- [ ] IF-0-ADAPTER-2 -- Boundary IR schema version emitted by the adapter is
  exactly `1.0`, matching `docs/interface-boundary-spec.md`.
- [ ] IF-0-ADAPTER-3 -- Node identity selection is frozen as
  `definition_id` -> `module + qualified_name` -> `node_id`, with the selected
  source recorded at `node.identity.source`.
- [ ] IF-0-ADAPTER-4 -- File records, node records, edge records, diagnostics,
  metrics, and run metadata use the frozen top-level keys from the schema spec.
- [ ] IF-0-ADAPTER-5 -- Canonical serialization API is frozen as
  `chunker.boundary.dumps_boundary_ir(ir, *, pretty=False) -> str` and always
  returns UTF-8-compatible JSON text with exactly one trailing newline.
- [ ] IF-0-ADAPTER-6 -- Canonical ordering is frozen as schema order for
  `files`, `nodes`, `edges`, `diagnostics`, and nested candidate/relationship ID
  lists.
- [ ] IF-0-ADAPTER-7 -- Phase 1 edge resolution maps current symbol graph data
  as `is_internal=True` to `resolved` and unresolved references to `unresolved`;
  no `ambiguous` edge is emitted until Phase 2 changes resolver semantics.
- [ ] IF-0-ADAPTER-8 -- CLI export entry point is frozen as
  `treesitter-chunker boundary <path> --lang <language> --output <file> [--pretty]`
  with stdout output when `--output` is omitted.
- [ ] IF-0-ADAPTER-9 -- Existing `chunk_file()`, `extract_symbol_graph()`, and
  non-boundary JSON exporters remain backward compatible.
- [ ] IF-0-ADAPTER-10 -- Canonical output omits volatile timestamps by default;
  `run.created_at` is `null` unless the caller supplies a stable value.

## Lane Index & Dependencies

- SL-0 -- Boundary module shell and identity helpers; Depends on: (none); Blocks: SL-1, SL-2, SL-3; Parallel-safe: no
- SL-1 -- IR adapter assembly; Depends on: SL-0; Blocks: SL-2, SL-3, SL-4; Parallel-safe: no
- SL-2 -- Canonical serialization and export helper; Depends on: SL-0, SL-1; Blocks: SL-3, SL-4; Parallel-safe: no
- SL-3 -- Public CLI and top-level exports; Depends on: SL-1, SL-2; Blocks: SL-4; Parallel-safe: no
- SL-4 -- Documentation and compatibility reducer; Depends on: SL-0, SL-1, SL-2, SL-3; Blocks: (none); Parallel-safe: no

## Lanes

### SL-0 -- Boundary Module Shell And Identity Helpers

- **Scope**: Create the boundary package foundation and deterministic identity helpers without changing extraction behavior.
- **Owned files**: `chunker/boundary/__init__.py`, `chunker/boundary/types.py`, `chunker/boundary/identity.py`, `tests/test_boundary_ir_identity.py`
- **Interfaces provided**: `BOUNDARY_IR_SCHEMA_VERSION = "1.0"`; `select_node_identity(chunk, module_name=None) -> dict[str, str]`; Boundary IR typed aliases or lightweight record helpers; IF-0-ADAPTER-2 and IF-0-ADAPTER-3.
- **Interfaces consumed**: `CodeChunk.definition_id`, `CodeChunk.node_id`, `CodeChunk.symbol_id`, `CodeChunk.file_id`, `CodeChunk.file_path`, `CodeChunk.metadata`; schema fields from `docs/interface-boundary-spec.md`.
- **Parallel-safe**: no
- **Tasks**:
  - test: Add focused tests that build `CodeChunk` instances and assert identity precedence chooses `definition_id`, then `module + qualified_name`, then `node_id`.
  - test: Cover `node.identity.source` values exactly as `definition_id`, `module + qualified_name`, and `node_id`.
  - impl: Create `chunker/boundary/` with a small public surface and no parser or CLI dependencies.
  - impl: Keep helpers deterministic and side-effect free; do not call `datetime.now()`, read files, or invoke parsers in this lane.
  - impl: Represent missing optional schema fields as `None`, `{}`, or `[]` according to `docs/interface-boundary-spec.md`.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_identity.py tests/test_definition_id.py`

### SL-1 -- IR Adapter Assembly

- **Scope**: Build Boundary IR dictionaries from chunk metadata plus symbol graph output for file and repository inputs.
- **Owned files**: `chunker/boundary/adapter.py`, `tests/test_boundary_ir_adapter.py`
- **Interfaces provided**: `extract_boundary_ir(path, language=None, *, canonical=True, created_at=None) -> dict[str, Any]`; file/node/edge/diagnostic/metric assembly; IF-0-ADAPTER-1, IF-0-ADAPTER-4, IF-0-ADAPTER-7, IF-0-ADAPTER-10.
- **Interfaces consumed**: `select_node_identity()` from SL-0; `chunk_file()` from `chunker.core`; `collect_source_files()` and `extract_symbol_graph()` from `chunker.symbol_graph`; current relationship fields `from`, `to`, `type`, `line`, `file`, `is_internal`.
- **Parallel-safe**: no
- **Tasks**:
  - test: Add a Python fixture repo test that asserts top-level keys, one file record, node IDs using `definition_id`, metrics totals, and deterministic unresolved-edge fields.
  - test: Add a JavaScript fixture repo test that asserts imports/calls become edge records and `is_internal=True` maps to `resolution == "resolved"`.
  - test: Add a Go test behind the existing `go` grammar availability skip pattern to assert core fields are populated when the grammar exists.
  - test: Add a double-call in-memory equality assertion at the dict level for the same fixture input with `created_at=None`.
  - impl: Collect files with the same path ordering as `collect_source_files()` and use `chunk_file(..., extract_metadata=True, include_retrieval_metadata=True)` for node substrate.
  - impl: Build file records with `compute_file_id()`, stable relative paths, language, content hash, parser identifier, status, and file diagnostic IDs.
  - impl: Build node records from chunks, preserving spans, symbol fields, qualified names, semantic paths, signatures, parent IDs, relationships, deterministic metadata, and provenance.
  - impl: Maintain an adapter-local map from current symbol graph IDs and `(file, line, qualified_name/name)` to Boundary IR node IDs so existing relationships can target canonical node IDs.
  - impl: Build edge records with deterministic IDs, `source`, `target`, `type`, `resolution`, `reference`, `candidates`, `location`, `provenance`, and `metadata`.
  - impl: Convert symbol graph `errors` into deterministic diagnostics and metrics counters without failing the whole run.
  - impl: Do not change `extract_symbol_graph()` resolver behavior in this phase.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_adapter.py tests/test_metadata_extraction.py tests/test_symbol_graph.py`

### SL-2 -- Canonical Serialization And Export Helper

- **Scope**: Add canonical Boundary IR JSON serialization and a file-writing helper while leaving legacy JSON exporters unchanged.
- **Owned files**: `chunker/boundary/serialization.py`, `chunker/export/boundary_ir.py`, `chunker/export/__init__.py`, `tests/test_boundary_ir_serialization.py`
- **Interfaces provided**: `dumps_boundary_ir(ir, *, pretty=False) -> str`; `write_boundary_ir(ir, output, *, pretty=False) -> None`; `BoundaryIRExporter`; IF-0-ADAPTER-5 and IF-0-ADAPTER-6.
- **Interfaces consumed**: Boundary IR dictionaries from SL-1; schema canonical JSON rules from `docs/interface-boundary-spec.md`.
- **Parallel-safe**: no
- **Tasks**:
  - test: Add serialization tests asserting compact output has lexicographic object key ordering, no extra whitespace, and exactly one trailing newline.
  - test: Add ordering tests for shuffled `files`, `nodes`, `edges`, `diagnostics`, and `candidates`.
  - test: Add file writer tests using `tmp_path` and explicit `encoding="utf-8"`.
  - impl: Implement a canonicalization pass that sorts schema lists and nested ID lists before `json.dumps(sort_keys=True, separators=(",", ":"))`.
  - impl: Implement `pretty=True` for human-readable output without changing the default canonical compact output.
  - impl: Add an export helper in `chunker/export/boundary_ir.py` instead of altering existing `JSONExporter` or `StructuredJSONExporter` behavior.
  - impl: Export the helper from `chunker/export/__init__.py` without changing existing `__all__` entries.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_serialization.py tests/test_export_json.py tests/test_export_jsonl.py`

### SL-3 -- Public CLI And Top-Level Exports

- **Scope**: Expose Boundary IR generation through the package API and packaged Typer CLI.
- **Owned files**: `chunker/__init__.py`, `cli/main.py`, `tests/test_boundary_ir_cli.py`
- **Interfaces provided**: top-level package export for `extract_boundary_ir`; Typer command `boundary`; IF-0-ADAPTER-8 and IF-0-ADAPTER-9.
- **Interfaces consumed**: `extract_boundary_ir()` from SL-1; `dumps_boundary_ir()` and `write_boundary_ir()` from SL-2; current Typer app conventions in `cli/main.py`.
- **Parallel-safe**: no
- **Tasks**:
  - test: Add `CliRunner` coverage for `boundary <path> --lang python` writing canonical JSON to stdout.
  - test: Add `CliRunner` coverage for `boundary <path> --lang python --output out.json` and assert the file contains parseable Boundary IR with `schema_version == "1.0"`.
  - test: Add compatibility assertions that existing `chunk --json` and `batch --output-format json` behavior still works.
  - impl: Add `extract_boundary_ir` to `chunker.__all__` without importing parser-heavy modules beyond the new boundary package.
  - impl: Add `@app.command("boundary")` to `cli/main.py` with `path`, `--lang/-l`, `--output/-o`, `--pretty`, and `--quiet` options following existing CLI style.
  - impl: Print only JSON to stdout when `--output` is omitted; print a concise summary only when writing to a file and not quiet.
  - impl: Leave the older argparse `chunker.cli` surface untouched unless execution discovers a package-script regression that requires it.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_cli.py tests/test_cli.py tests/test_cli_integration_advanced.py`

### SL-4 -- Documentation And Compatibility Reducer

- **Scope**: Review whether the new public API and CLI require docs updates, and verify no existing extraction/export contracts regressed.
- **Owned files**: `docs/user-guide.md`, `docs/interface-boundary-roadmap.md`, `tests/test_boundary_ir_contract.py`
- **Interfaces provided**: final contract assertions for IF-0-ADAPTER-1 through IF-0-ADAPTER-10; any minimal user-facing command documentation if needed.
- **Interfaces consumed**: all interfaces from SL-0, SL-1, SL-2, and SL-3; `docs/interface-boundary-spec.md`; existing roadmap notes in `docs/interface-boundary-roadmap.md`.
- **Parallel-safe**: no
- **Tasks**:
  - test: Add contract tests that validate emitted Boundary IR has the frozen top-level keys and required metrics keys for a compact Python fixture.
  - test: Add compatibility tests or assertions only where gaps remain after SL-1 through SL-3; do not duplicate lower-lane fixture coverage unnecessarily.
  - impl: If the CLI command or public API names differ from current docs, add a minimal user-guide example for `treesitter-chunker boundary`.
  - impl: If `docs/interface-boundary-roadmap.md` already describes the adapter accurately, leave it unchanged and record that no docs edit was needed in execution notes.
  - impl: Do not alter `docs/interface-boundary-spec.md` in this phase unless execution reveals an implementation-blocking schema ambiguity; such a change would require stopping for schema approval.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_contract.py`
  - verify: `uv run --with toml --all-extras mkdocs build --strict`

## Verification

Planning-only runs should not execute verification. During execution, run
targeted checks first, then the local-first repo checks from `AGENTS.md`:

```bash
uv run --with toml --all-extras pytest tests/test_boundary_ir_identity.py tests/test_boundary_ir_adapter.py tests/test_boundary_ir_serialization.py tests/test_boundary_ir_cli.py tests/test_boundary_ir_contract.py
uv run --with toml --all-extras pytest tests/test_definition_id.py tests/test_metadata_extraction.py tests/test_symbol_graph.py tests/test_export_json.py tests/test_export_jsonl.py tests/test_cli.py
uv run --with toml --all-extras mkdocs build --strict
uv run --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
uv run --all-extras black --check chunker/ cli/ tests/ scripts/
uv run --with toml --all-extras python scripts/run_ci_smoke.py
```

Because this phase touches paths, extraction, and export formatting, run the
standing Windows preflight before pushing:

```bash
ssh leno 'powershell -NoProfile -Command "cd $HOME\\code\\treesitter-chunker; git fetch origin; git checkout main; git pull --ff-only; uv run --with toml --all-extras python scripts/run_windows_preflight.py"'
```

## Acceptance Criteria

- [ ] `chunker.boundary.extract_boundary_ir()` can generate Boundary IR from a file or repository path.
- [ ] The adapter calls `chunk_file(..., extract_metadata=True, include_retrieval_metadata=True)` for chunk/node data.
- [ ] The adapter incorporates `extract_symbol_graph()` relationship output without changing existing symbol graph behavior.
- [ ] Emitted Boundary IR contains `schema_version`, `source`, `files`, `nodes`, `edges`, `diagnostics`, `metrics`, and `run`.
- [ ] Nodes use deterministic identity precedence: `definition_id` -> `module + qualified_name` -> `node_id`.
- [ ] Duplicate nodes and edges are deterministically deduplicated.
- [ ] Files, nodes, edges, diagnostics, and nested candidate/relationship ID lists are emitted in canonical order.
- [ ] Canonical JSON output is compact, sorted, UTF-8-compatible, and has exactly one trailing newline.
- [ ] `treesitter-chunker boundary` can write canonical JSON to stdout or a requested output file.
- [ ] `run.created_at` is `null` by default in canonical output.
- [ ] Existing chunking, symbol graph, and legacy JSON export tests continue to pass.
- [ ] Phase 1 does not implement strict/permissive ambiguity semantics, incremental recomputation, semantic resolver integrations, or ownership policy enforcement.
