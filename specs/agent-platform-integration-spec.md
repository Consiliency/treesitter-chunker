## Agent Platform Integration Spec (Stable IDs, XRef Graph, Export, APIs)

- File: specs/agent-platform-integration-spec.md
- Owner: Core Chunker Team
- Status: Proposal
- Scope: Implement requested changes in `docs/requested-changes-dfrom-chunger-lib.md` with full test coverage
- Non-goal: No code changes in this MR; this is the implementation spec only

### Objectives

- Add stable, byte-accurate spans and node IDs
  - For each chunk: file_id, symbol_id, start_byte, end_byte, start_line, end_line
  - node_id = sha1(path + language + ast_route + text_hash16)
- Expose chunk hierarchy + xref graph
  - Parent route (list of ancestor node_types)
  - Edges: defines, calls, imports, inherits, references (src_id, dst_id, type)
- Token awareness and packing hints
  - token_count(model="claude-3.5") per chunk
  - pack_hint: priority score for context packing (size/importance)
- Incremental re-index
  - Watch mode; only changed files; update nodes/edges/spans
- Postgres exporter (spec)
  - Tables: nodes(id, file, lang, symbol, kind, attrs jsonb)
           edges(src, dst, type, weight)
           spans(file_id, symbol_id, start_byte, end_byte)
  - Upsert by (id) with change_version
- GraphCut endpoint
  - Input: seeds[], radius, budget, rank weights (distance/publicness/hotspots)
  - Output: node_ids[], edges[] (minimal cut)
- Nearest-tests helper
  - For a set of symbols, return candidate test files + rationale
- Metrics
  - Timings per stage, cache hit rate, files/min, memory high-water

### Deliverables

- Data model updates in `chunker/types.py`
- AST traversal updates in `chunker/core.py` and `chunker/streaming.py`
- XRef builder `chunker/graph/xref.py` and GraphCut `chunker/graph/cut.py`
- Token packing hints `chunker/packing.py`; token counter model update
- Incremental watch in `chunker/repo/processor.py`
- Postgres spec exporter `chunker/export/postgres_spec_exporter.py`
- API additions in `api/server.py`
- Tests (unit, integration, performance) per plan below
- Back-compat with existing exporters/clients

## Data Model

### CodeChunk changes (`chunker/types.py`)

- Add fields:
  - `node_id: str` (stable id; also set `chunk_id` to same for back-compat)
  - `file_id: str`
  - `symbol_id: str | None`
  - `parent_route: list[str]` (ancestor node types from root to this node)
- Keep `byte_start`/`byte_end` (byte-accurate spans).
- Place mirrors in `metadata` for API/export convenience:
  - `metadata.start_byte`, `metadata.end_byte`, `metadata.parent_route` (optional if fields already present).

ID computation:
- `text_hash16 = sha1(content)[:16]`
- `ast_route = "/".join(parent_route)`
- `node_id = sha1(f"{file_path}|{language}|{ast_route}|{text_hash16}")`
- `file_id = sha1(f"file:{file_path}")`
- `symbol_id = sha1(f"sym:{language}:{file_path}:{symbol_name}")` if symbol_name known

Helpers (new, internal):
- `compute_node_id(file_path, language, parent_route, content)`
- `compute_file_id(file_path)`
- `compute_symbol_id(language, file_path, symbol_name)`

Back-compat:
- `chunk_id` remains but equals `node_id`.

## AST Traversal and Streaming

### Core traversal (`chunker/core.py`)

- `_walk(...)`:
  - Thread a `parent_route: list[str]` argument (copy on descend).
  - On chunk creation:
    - Set `parent_route`, `parent_chunk_id` = parent.node_id (not chunk_id alias).
    - Compute `node_id` (temporary; recompute after `file_path` set).
    - Extract symbol name from `MetadataExtractorFactory` (signature) if available; compute `symbol_id`.
  - Recurse to children with updated `parent_route`.

- `chunk_text(...)`:
  - After `_walk`, set `file_path` on chunks, compute `file_id`, recompute `node_id` with path.

- `chunk_file(...)`:
  - No change beyond delegating to `chunk_text`.

### Streaming traversal (`chunker/streaming.py`)

- `_walk_streaming(...)`:
  - Add `parent_route` threading analogous to core.
  - Fill `node_id`, `parent_chunk_id`, `parent_route`.
- `chunk_file_streaming(...)`:
  - Ensure byte-span derived IDs identical to non-streaming path.

## XRef Graph and GraphCut

### XRef builder (`chunker/graph/xref.py`)

- Function: `build_xref(chunks: list[CodeChunk]) -> tuple[list[dict], list[dict]]`
  - Nodes: `{ id, file, lang, symbol, kind, attrs }` from `CodeChunk`.
  - Edges:
    - `DEFINES`: parent → child using `parent_chunk_id`.
    - `IMPORTS`: from `chunk.metadata["imports"]` to matched target chunks.
    - `CALLS`: from `chunk.metadata.get("calls")` or inferred via `SymbolResolver`.
    - `INHERITS`: language-specific metadata (extends/implements).
    - `REFERENCES`: via `BaseSymbolResolver.find_symbol_references(...)`.
- Use `chunker/context/symbol_resolver.py` helpers where possible.

### GraphCut (`chunker/graph/cut.py`)

- Function: `graph_cut(seeds, nodes, edges, radius, budget, weights) -> (node_ids, edges)`
  - BFS/expansion limited by `radius`.
  - Score nodes: `score = w_distance * (1/d) + w_publicness * deg_out + w_hotspots * change_freq` (fallback to deg when hotspot unknown).
  - Return minimal set under `budget` with edges among selected nodes.

## Token Awareness and Packing Hints

### Token counting (`chunker/token/counter.py`)

- Add model: `claude-3.5` mapping to `cl100k_base`, token limit 200k (or best known).

### Packing hints (`chunker/packing.py`)

- Function: `compute_pack_hint(chunk) -> float`
  - Inputs: `token_count`, `complexity`, `degree` (xref), `recent_changes`, optional priority metadata.
  - Output: normalized score [0, 1].
- Add in `TreeSitterTokenAwareChunker.add_token_info(...)`:
  - Set `metadata["token_count"]` and `metadata["pack_hint"]`.

## Incremental Re-index

### Watch mode (`chunker/repo/processor.py`)

- Add `watch_repository(repo_path: str, on_update: Callable, poll_interval: float = 1.0)`
  - Detect changes via git + hash fallback (see `docs/cookbook.md` changed files snippet).
  - Re-chunk only changed files.
  - Emit deltas: nodes (added/updated/removed), edges, spans.
  - Optionally integrate `chunker/incremental.py` for diffs.

## Postgres Exporter (Spec-compliant)

### New exporter (`chunker/export/postgres_spec_exporter.py`)

- Schema:
  - `nodes(id text primary key, file text, lang text, symbol text, kind text, attrs jsonb, change_version int default 1)`
  - `edges(src text, dst text, type text, weight numeric default 1)`
  - `spans(file_id text, symbol_id text, start_byte int, end_byte int)`
- Upsert:
  - `INSERT ... ON CONFLICT (id) DO UPDATE SET change_version = nodes.change_version + 1, attrs = EXCLUDED.attrs`
- Export entry:
  - `export(repo_root: str, config: dict) -> int` returning `rows_written`.
- Prefer direct DB (psycopg) if DSN present; else generate SQL.

Back-compat:
- Keep existing `chunker/export/postgres_exporter.py` (advanced script generator).

## HTTP API Extensions (`api/server.py`)

- Add models:
  - `ExportPostgresRequest { repo_root: str, config?: dict } -> { rows_written: int }`
  - `GraphXrefRequest { paths: list[str] } -> { nodes: list[...], edges: list[...] }`
  - `GraphCutRequest { seeds: list[str], params: { radius?: int, budget?: int, weights?: { distance?: float, publicness?: float, hotspots?: float } } } -> { nodes: list[str], edges: list[...] }`
  - `NearestTestsRequest { symbols: list[str] } -> { tests: [{ path, score, symbols }] }`
- Endpoints:
  - `POST /export/postgres`
  - `POST /graph/xref`
  - `POST /graph/cut`
  - `POST /nearest-tests`
- Return timings in response `metadata` (optional).

## Nearest-Tests Helper (`chunker/helpers/nearest_tests.py`)

- `nearest_tests(symbols, repo_root) -> list[{ path, score, symbols }]`
  - Heuristics: file naming (`test_*.py`, `*_test.*`), same module/package proximity, references/import proximity, content match, recency.

## Metrics

- Use `chunker/performance/optimization/monitor.py`:
  - Record: stage timings, cache hit rate, files/min, memory high-water where available.
- Optional `GET /metrics` to expose summary.

## Backward Compatibility and Migration

- `chunk_id` remains but aliases `node_id`.
- Exporters:
  - `chunker/export/database_exporter_base.py` `_get_chunk_id` should use `chunk.node_id or chunk.chunk_id`.
- Ensure JSON response shapes unchanged unless using new endpoints.

## Risks and Mitigations

- ID changes affecting external consumers → keep `chunk_id` alias and document.
- Language-specific symbol extraction variance → fall back gracefully and log.
- GraphCut quality → expose weights in API to tune.

## Testing Plan

### Existing tests to run (confirmed)

- `tests/test_phase12_integration.py` (DB/graph exports)
- `tests/test_token_integration.py` (token counting and chunk splitting)
- `tests/test_intelligent_fallback.py` (fallback correctness)
- `tests/test_performance_features.py` (monitoring basics)
- `tests/test_hierarchy.py` (hierarchy navigation)

### Existing tests to verify presence (from roadmap; run if present)

- `tests/test_phase11_comprehensive_integration.py`
- `tests/test_language_config.py`
- `tests/test_language_integration.py`
- `tests/test_config_advanced_scenarios.py`
- `tests/test_phase10_full_integration.py`

### New unit tests to add

- `tests/test_spans_roundtrip.py`
  - Slice by `byte_start:byte_end` equals original file content.
- `tests/test_node_id_stability.py`
  - Stable `node_id` across runs and unaffected by unrelated changes.
- `tests/test_codechunk_ids_backcompat.py`
  - `chunk_id == node_id` and exporters prefer `node_id`.
- `tests/test_xref_graph.py`
  - Nodes and edges for defines/imports/calls/inherits/references.
- `tests/test_graph_cut.py`
  - Correct radius expansion, budget adherence, weight effects.
- `tests/test_nearest_tests.py`
  - Returns plausible candidates with non-zero scores and rationale.
- `tests/test_postgres_spec_exporter.py`
  - DDL matches spec; upsert increments `change_version`; spans populated.
- `tests/test_incremental_watch.py`
  - Only changed files updated; nodes/edges deltas correct.
- `tests/test_api_endpoints_extended.py`
  - New endpoints request/response contracts.
- `tests/test_packing_hint.py`
  - `compute_pack_hint` monotonic wrt token_count and degree.

### Integration and performance tests

- `tests/integration/test_repo_watch_end_to_end.py`
  - Start watch; modify files; verify deltas and metrics.
- `tests/perf/test_large_repo_incremental.py`
  - Measure files/min; ensure within threshold; verify cache hit rate metric.
- `tests/integration/test_streaming_ids_consistency.py`
  - Streaming vs non-streaming produce identical IDs and spans.

### Manual validation

- Chunk a representative repo; export Postgres; run basic queries.
- Verify GraphCut on known seeds yields expected minimal subgraph.
- Validate nearest-tests suggestions on a repo with clear test conventions.

### Test commands

- Lint/typecheck:
  - `ruff check chunker/ tests/`
  - `black --check chunker/ tests/`
  - `mypy chunker/ tests/`
- Unit tests:
  - `pytest -xvs -m "not integration"`
- Integration tests:
  - `pytest -xvs -m "integration"`

## Implementation Sequence

1. Data model changes in `chunker/types.py` with helpers.
2. Update traversals in `chunker/core.py` and `chunker/streaming.py`.
3. Update exporters to prefer `node_id`; add Postgres spec exporter.
4. Add XRef builder and GraphCut modules.
5. Add packing hint; extend token counter for `claude-3.5`.
6. Add watch mode API in repo processor.
7. Extend FastAPI endpoints.
8. Wire metrics.
9. Implement tests; stabilize.

## Acceptance Criteria

- All updated and new tests pass locally and in CI.
- IDs are stable and byte-accurate spans round-trip.
- XRef edges extracted correctly for at least Python/JS.
- Postgres spec exporter produces schema and upserts with `change_version`.
- New endpoints function per contracts with timings recorded.
- No regressions in existing chunking, exporters, or CLI. 